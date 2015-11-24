import os
import unittest
import tarfile
from copy import deepcopy

from netjsonconfig import OpenWisp
from netjsonconfig.exceptions import ValidationError
from netjsonconfig.utils import _TabsMixin


class TestBackend(unittest.TestCase, _TabsMixin):
    """
    tests for OpenWisp backend
    """
    config = {
        "general": {
            "hostname": "openwisp_test"
        },
        "interfaces": [
            {
                "name": "tap0",
                "type": "virtual"
            },
            {
                "network": "serv",
                "name": "br-serv",
                "type": "bridge",
                "bridge_members": [
                    "tap0"
                ],
                "addresses": [
                    {
                        "proto": "static",
                        "family": "ipv4",
                        "address": "192.168.1.2",
                        "mask": 24
                    }
                ]
            },
            {
                "name": "wlan0",
                "type": "wireless",
                "wireless": {
                    "radio": "radio0",
                    "mode": "access_point",
                    "ssid": "wifi-service",
                    "isolate": True,
                    "network": ["wlan1", "serv"]
                }
            }
        ],
        "radios": [
            {
                "name": "radio0",
                "phy": "phy0",
                "driver": "mac80211",
                "protocol": "802.11n",
                "channel": 11,
                "channel_width": 20,
                "tx_power": 5,
                "country": "IT"
            }
        ],
        "openvpn": [
            {
                "config_name": "openvpn",
                "config_value": "2693",
                "enabled": "1",
                "client": "1",
                "dev": "tap0",
                "dev_type": "tap",
                "proto": "tcp-client",
                "remote": "vpn.openwisp.org 12128",
                "nobind": "1",
                "keepalive": "5 40",
                "ns_cert_type": "server",
                "resolv_retry": "infinite",
                "comp_lzo": "yes",
                "tls_client": "1",
                "ca": "/tmp/owispmanager/openvpn/x509/ca_1_service.pem",
                "key": "/tmp/owispmanager/openvpn/x509/l2vpn_client_2693.pem",
                "cert": "/tmp/owispmanager/openvpn/x509/l2vpn_client_2693.pem",
                "up": "/tmp/owispmanager/openvpn/vpn_2693_script_up.sh",
                "down": "/tmp/owispmanager/openvpn/vpn_2693_script_down.sh",
                "cipher": "AES-128-CBC",
                "script_security": "3",
                "up_delay": "1",
                "up_restart": "1",
                "persist_tun": "1",
                "mute_replay_warnings": "1",
                "verb": "1",
                "mute": "10",
                "log": "/tmp/openvpn_2693.log"
            }
        ],
        "files": [
            {
                "path": "/openvpn/x509/ca_1_service.pem",
                "contents": "-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n"
            },
            {
                "path": "/openvpn/x509/l2vpn_client_2693.pem",
                "contents": "-----BEGIN CERTIFICATE-----\ntest==\n-----END CERTIFICATE-----\n-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----\n"
            }
        ]
    }

    def test_uci(self):
        o = OpenWisp({
            "general": {
                "hostname": "openwisp_test"
            }
        })
        o.generate()
        tar = tarfile.open('openwrt-config.tar.gz', 'r:gz')
        system = tar.getmember('uci/system.conf')
        contents = tar.extractfile(system).read().decode()
        expected = self._tabs("""package system

config system
    option hostname 'openwisp_test'
    option timezone 'UTC'
""")
        self.assertEqual(contents, expected)
        # close and delete tar.gz file
        tar.close()
        os.remove('openwrt-config.tar.gz')

    def test_hostname_required(self):
        o = OpenWisp({
            "general": {
                "timezone": "Coordinated Universal Time"
            }
        })
        with self.assertRaises(ValidationError):
            o.validate()

    def test_install_script(self):
        config = deepcopy(self.config)
        o = OpenWisp(config)
        o.generate()
        tar = tarfile.open('openwrt-config.tar.gz', 'r:gz')
        install = tar.getmember('install.sh')
        contents = tar.extractfile(install).read().decode()
        self.assertIn('openvpn --mktun --dev 2693 --dev-type tap', contents)
        self.assertIn('ifup br-serv', contents)
        self.assertIn('$(ip address show dev br-serv | grep 192.168.1.2)', contents)
        self.assertIn('wifi up radio0', contents)
        # esure is executable
        self.assertEqual(install.mode, 493)
        # close and delete tar.gz file
        tar.close()
        os.remove('openwrt-config.tar.gz')

    def test_ensure_tun_vpn_ignored(self):
        config = deepcopy(self.config)
        config['openvpn'][0]['dev_type'] = 'tun'
        o = OpenWisp(config)
        o.generate()
        tar = tarfile.open('openwrt-config.tar.gz', 'r:gz')
        install = tar.getmember('install.sh')
        contents = tar.extractfile(install).read().decode()
        self.assertNotIn('openvpn --mktun --dev 2693 --dev-type tap', contents)
        # close and delete tar.gz file
        tar.close()
        os.remove('openwrt-config.tar.gz')

    def test_uninstall_script(self):
        config = deepcopy(self.config)
        o = OpenWisp(config)
        o.generate()
        tar = tarfile.open('openwrt-config.tar.gz', 'r:gz')
        uninstall = tar.getmember('uninstall.sh')
        contents = tar.extractfile(uninstall).read().decode()
        self.assertIn('openvpn --rmtun --dev 2693 --dev-type tap', contents)
        # esure is executable
        self.assertEqual(uninstall.mode, 493)
        # close and delete tar.gz file
        tar.close()
        os.remove('openwrt-config.tar.gz')

    def test_up_and_down_scripts(self):
        config = deepcopy(self.config)
        o = OpenWisp(config)
        o.generate()
        tar = tarfile.open('openwrt-config.tar.gz', 'r:gz')
        up = tar.getmember('openvpn/vpn_2693_script_up.sh')
        contents = tar.extractfile(up).read().decode()
        self.assertIn('rm -f /tmp/will_reboot', contents)
        self.assertEqual(up.mode, 493)  # esure is executable
        down = tar.getmember('openvpn/vpn_2693_script_down.sh')
        contents = tar.extractfile(down).read().decode()
        self.assertIn('REBOOT_DELAY', contents)
        self.assertEqual(down.mode, 493)  # esure is executable
        # close and delete tar.gz file
        tar.close()
        os.remove('openwrt-config.tar.gz')

    def test_double_generation(self):
        o = OpenWisp(self.config)
        o.generate()
        o.generate()

    def test_wireless_radio_disabled_0(self):
        o = OpenWisp({
            'radios': self.config['radios']
        })
        output = o.render()
        self.assertIn("option disabled '0'", output)
