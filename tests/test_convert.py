import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("converter", ROOT / "convert.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)

class ConverterTests(unittest.TestCase):
    def test_domains_strip_dns_and_deduplicate(self):
        self.assertEqual(c.parse_domains("server=/QQ.COM/1.1.1.1\nserver=/qq.com/8.8.8.8\n"), ["qq.com"])
    def test_parent_domain_covers_children(self):
        self.assertEqual(c.parse_domains("server=/cn/1.1.1.1\nserver=/a.cn/1.1.1.1\n"), ["cn"])
    def test_invalid_domains_are_rejected(self):
        for value in ('server=/bad";remove/1.1.1.1', 'server=/good.com/', '<html>error</html>', ''):
            with self.subTest(value=value), self.assertRaises(ValueError):
                c.parse_domains(value)
    def test_ipv4_merge(self):
        self.assertEqual(c.parse_ipv4("1.0.1.0/24\n1.0.0.0/24\n1.0.1.0/24\n"), ["1.0.0.0/23"])
    def test_invalid_ipv4_are_rejected(self):
        for value in ('2001:db8::/32', '10.0.0.0/8', '1.0.1.1/24', '', '<html>error</html>'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                c.parse_ipv4(value)
    def test_outputs_do_not_contain_dns_addresses(self):
        files = c.render(['1.0.0.0/24'], ['qq.com'])
        self.assertEqual(files['china-domains.txt'], 'qq.com\n')
        self.assertNotIn('forward-to', files['china-domains.rsc'])
        self.assertIn('list="CN" comment="routeros-china-lists:ipv4"', files['CN.rsc'])
    def test_cli_output_and_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            (p/'ip.txt').write_text('1.0.0.0/24\n')
            (p/'dns.conf').write_text('server=/qq.com/1.1.1.1\n')
            result = subprocess.run([sys.executable, str(ROOT/'convert.py'), '--ip-file', str(p/'ip.txt'), '--domain-file', str(p/'dns.conf'), '--output', str(p/'out')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((p/'out/china-domains.txt').read_text(), 'qq.com\n')
            import hashlib
            self.assertIn(hashlib.sha256((p/'out/CN.rsc').read_bytes()).hexdigest() + '  CN.rsc', (p/'out/SHA256SUMS').read_text())

if __name__ == '__main__':
    unittest.main()
