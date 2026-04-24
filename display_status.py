# display_status.py
import requests
import time
import os

BASE = 'http://127.0.0.1:8080'

def clear():
    os.system('clear')

def color(text, code):
    return f"\033[{code}m{text}\033[0m"

def display():
    while True:
        try:
            clear()
            print(color("=" * 65, '36'))
            print(color("   PORT STATUS MONITORING TOOL — LIVE VIEW", '1;36'))
            print(color(f"   {time.strftime('%Y-%m-%d %H:%M:%S')}", '36'))
            print(color("=" * 65, '36'))

            r = requests.get(f'{BASE}/status', timeout=3)

            if not r.text.strip():
                print(color("\n  Controller connected, waiting for switch data...", '33'))
                time.sleep(2)
                continue

            try:
                data = r.json()
            except Exception:
                print(color(f"\n  Bad response: {r.text[:200]}", '31'))
                time.sleep(2)
                continue

            # Port status table
            print(color("\n  SWITCH PORT STATUS", '1;33'))
            print(color("  " + "-" * 60, '33'))

            port_status = data.get('port_status', {})
            if not port_status:
                print(color("  No switch data yet — run pingall in Mininet first.", '33'))
            else:
                for dpid, ports in port_status.items():
                    print(f"\n  Switch: {color(dpid, '1')}")
                    print(f"  {'Port':<6} {'Name':<12} {'State':<10} {'UP Events':<12} {'DOWN Events':<12} Last Change")
                    print(f"  {'-'*72}")
                    for pno, info in ports.items():
                        state = info.get('state', '?')
                        if state == 'UP':
                            state_str = color("● UP  ", '1;32')
                        else:
                            state_str = color("● DOWN", '1;31')
                        print(f"  {pno:<6} {info.get('name','?'):<12} {state_str}    "
                              f"{info.get('up_events',0):<12} {info.get('down_events',0):<12} "
                              f"{info.get('last_change','?')}")

            # Alerts
            print(color("\n  RECENT ALERTS", '1;33'))
            print(color("  " + "-" * 60, '33'))
            alerts = data.get('recent_alerts', [])
            if not alerts:
                print(color("  No alerts yet — try: link s1 s2 down  in Mininet", '2'))
            else:
                for a in alerts:
                    if a['severity'] == 'WARNING':
                        icon = color("⚠  LINK_DOWN", '1;31')
                    else:
                        icon = color("✓  LINK_UP  ", '1;32')
                    print(f"  {icon} | {a['timestamp']} | Port {a['port_no']} ({a['port_name']})")

            print(color(f"\n  Total alerts: {data.get('alert_count', 0)}", '36'))
            print(color("  Refreshing every 2s... Ctrl+C to stop", '2'))

        except requests.exceptions.ConnectionError:
            print(color("\n  Waiting for controller at 127.0.0.1:8080...", '33'))
        except Exception as e:
            print(color(f"\n  Error: {e}", '31'))

        time.sleep(2)

if __name__ == '__main__':
    display()