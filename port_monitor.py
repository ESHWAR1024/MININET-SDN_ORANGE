# port_monitor.py
# Port Status Monitoring Tool — Ryu Controller
    
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types
from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from webob import Response
import json
import logging
import datetime

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler('port_status.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('PortMonitor')
APP_KEY = 'port_monitor_app'
# ───────────────────────────────────────────────────────────────────────────────


def make_response(data):
    """Helper — always returns bytes body, avoids webob encode errors."""
    return Response(
        content_type='application/json',
        charset='utf-8',
        body=json.dumps(data, indent=2, default=str).encode('utf-8')
    )


class PortStatusMonitor(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(PortStatusMonitor, self).__init__(*args, **kwargs)
        self.port_status = {}   # {dpid_str: {port_str: info_dict}}
        self.mac_to_port = {}   # {dpid_str: {mac: port_no}}
        self.alerts      = []   # list of alert dicts
        self.change_log  = []   # list of change dicts

        kwargs['wsgi'].register(PortStatusAPI, {APP_KEY: self})

        logger.info("=" * 60)
        logger.info("  Port Status Monitoring Tool — Controller Started")
        logger.info("  REST API: http://127.0.0.1:8080/status")
        logger.info("=" * 60)

    # ── Switch connects ────────────────────────────────────────────────────────
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp     = ev.msg.datapath
        ofp    = dp.ofproto
        parser = dp.ofproto_parser
        dpid   = str(dp.id)

        self.port_status[dpid] = {}
        self.mac_to_port[dpid] = {}

        logger.info(f"Switch connected | DPID: {dp.id}")

        # Table-miss rule — send unknown packets to controller
        match   = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        inst    = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        mod     = parser.OFPFlowMod(datapath=dp, priority=0, match=match, instructions=inst)
        dp.send_msg(mod)

        # Request port list
        dp.send_msg(parser.OFPPortDescStatsRequest(dp, 0))

    # ── Initial port inventory ─────────────────────────────────────────────────
    @set_ev_cls(ofp_event.EventOFPPortDescStatsReply, MAIN_DISPATCHER)
    def port_desc_reply_handler(self, ev):
        dp   = ev.msg.datapath
        dpid = str(dp.id)

        for p in ev.msg.body:
            if p.port_no >= 0xFFFFFF00:
                continue
            state = 'DOWN' if (p.state & 0x1) else 'UP'
            name  = p.name.decode('utf-8').rstrip('\x00')
            self.port_status[dpid][str(p.port_no)] = {
                'name':        name,
                'state':       state,
                'hw_addr':     str(p.hw_addr),
                'last_change': self._now(),
                'up_events':   1 if state == 'UP' else 0,
                'down_events': 0,
            }
            logger.info(f"  Port inventory | Switch {dp.id} | Port {p.port_no} ({name}) | {state}")

    # ── Port status change — CORE FEATURE ─────────────────────────────────────
    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def port_status_handler(self, ev):
        msg    = ev.msg
        dp     = msg.datapath
        dpid   = str(dp.id)
        ofp    = dp.ofproto
        desc   = msg.desc
        pno    = str(desc.port_no)
        pname  = desc.name.decode('utf-8').rstrip('\x00')
        ts     = self._now()

        reason_map = {
            ofp.OFPPR_ADD:    'PORT_ADDED',
            ofp.OFPPR_DELETE: 'PORT_DELETED',
            ofp.OFPPR_MODIFY: 'PORT_MODIFIED',
        }
        reason_str = reason_map.get(msg.reason, 'UNKNOWN')
        new_state  = 'DOWN' if (desc.state & ofp.OFPPS_LINK_DOWN) else 'UP'

        # Get previous state
        old_state = 'UNKNOWN'
        if dpid in self.port_status and pno in self.port_status[dpid]:
            old_state = self.port_status[dpid][pno].get('state', 'UNKNOWN')

        # Update state table
        if dpid not in self.port_status:
            self.port_status[dpid] = {}
        entry = self.port_status[dpid].setdefault(pno, {'up_events': 0, 'down_events': 0})
        entry.update({
            'name':        pname,
            'state':       new_state,
            'hw_addr':     str(desc.hw_addr),
            'last_change': ts,
        })
        if new_state == 'UP':
            entry['up_events'] = entry.get('up_events', 0) + 1
        else:
            entry['down_events'] = entry.get('down_events', 0) + 1

        # Log change
        self.change_log.append({
            'timestamp': ts,
            'dpid':      dpid,
            'port_no':   pno,
            'port_name': pname,
            'reason':    reason_str,
            'old_state': old_state,
            'new_state': new_state,
        })
        logger.info(
            f"PORT CHANGE | Switch {dp.id} | Port {pno} ({pname}) | "
            f"{old_state} -> {new_state} | {reason_str}"
        )

        # Alerts
        if new_state == 'DOWN' and old_state == 'UP':
            self._alert('LINK_DOWN', 'WARNING', dpid, pno, pname, ts)
            self.mac_to_port[dpid] = {}   # flush MAC table
        elif new_state == 'UP' and old_state in ('DOWN', 'UNKNOWN'):
            self._alert('LINK_UP', 'INFO', dpid, pno, pname, ts)

    # ── Packet-in: learning switch ─────────────────────────────────────────────
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg     = ev.msg
        dp      = msg.datapath
        ofp     = dp.ofproto
        parser  = dp.ofproto_parser
        dpid    = str(dp.id)
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        src = eth.src
        dst = eth.dst

        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port

        out_port = self.mac_to_port[dpid].get(dst, ofp.OFPP_FLOOD)
        actions  = [parser.OFPActionOutput(out_port)]

        if out_port != ofp.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            inst  = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
            if msg.buffer_id != ofp.OFP_NO_BUFFER:
                mod = parser.OFPFlowMod(
                    datapath=dp, buffer_id=msg.buffer_id,
                    priority=1, match=match, instructions=inst
                )
                dp.send_msg(mod)
                return
            else:
                mod = parser.OFPFlowMod(
                    datapath=dp, priority=1, match=match, instructions=inst
                )
                dp.send_msg(mod)

        data = None if msg.buffer_id != ofp.OFP_NO_BUFFER else msg.data
        dp.send_msg(parser.OFPPacketOut(
            datapath=dp, buffer_id=msg.buffer_id,
            in_port=in_port, actions=actions, data=data
        ))

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _alert(self, atype, severity, dpid, pno, pname, ts):
        entry = {
            'timestamp': ts,
            'type':      atype,
            'severity':  severity,
            'dpid':      dpid,
            'port_no':   pno,
            'port_name': pname,
            'message':   f"ALERT [{severity}] {atype} | Switch {dpid} | Port {pno} ({pname}) | {ts}",
        }
        self.alerts.append(entry)
        log_fn = logger.warning if severity == 'WARNING' else logger.info
        log_fn("=" * 55)
        log_fn(f"  {'!!' if severity == 'WARNING' else '>>'} {entry['message']}")
        log_fn("=" * 55)

    @staticmethod
    def _now():
        return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ── REST API ───────────────────────────────────────────────────────────────────
class PortStatusAPI(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(PortStatusAPI, self).__init__(req, link, data, **config)
        self.app = data[APP_KEY]

    @route('portmonitor', '/status', methods=['GET'])
    def get_status(self, req, **_):
        return make_response({
            'port_status':   self.app.port_status,
            'alert_count':   len(self.app.alerts),
            'recent_alerts': self.app.alerts[-5:],
        })

    @route('portmonitor', '/alerts', methods=['GET'])
    def get_alerts(self, req, **_):
        return make_response(self.app.alerts)

    @route('portmonitor', '/log', methods=['GET'])
    def get_log(self, req, **_):
        return make_response(self.app.change_log)