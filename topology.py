# topology.py
from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info

def build_topology():
    net = Mininet(
        controller=RemoteController,
        switch=OVSKernelSwitch,
        autoSetMacs=False
    )

    info('*** Adding remote controller\n')
    net.addController('c0',
                      controller=RemoteController,
                      ip='127.0.0.1',
                      port=6633)

    info('*** Adding switches\n')
    s1 = net.addSwitch('s1', protocols='OpenFlow13')
    s2 = net.addSwitch('s2', protocols='OpenFlow13')

    info('*** Adding hosts\n')
    h1 = net.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
    h2 = net.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
    h3 = net.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')
    h4 = net.addHost('h4', ip='10.0.0.4/24', mac='00:00:00:00:00:04')

    info('*** Adding links\n')
    net.addLink(h1, s1)
    net.addLink(h2, s1)
    net.addLink(h3, s2)
    net.addLink(h4, s2)
    net.addLink(s1, s2)   # inter-switch monitored link

    info('*** Starting network\n')
    net.start()

    info('*** Setting OpenFlow 1.3\n')
    s1.cmd('ovs-vsctl set bridge s1 protocols=OpenFlow13')
    s2.cmd('ovs-vsctl set bridge s2 protocols=OpenFlow13')

    info('\nTopology ready!\n')
    info('  h1 (10.0.0.1) --|\n')
    info('                   s1 ------- s2\n')
    info('  h2 (10.0.0.2) --|           |-- h3 (10.0.0.3)\n')
    info('                              |-- h4 (10.0.0.4)\n\n')

    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    build_topology()