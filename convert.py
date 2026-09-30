#!/usr/bin/env python3
"""Build CN address lists and DNS-address-free domain lists. Standard library only."""
import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import sys
import time
import urllib.request

SOURCES = {
    "ipv4": "https://raw.githubusercontent.com/misakaio/chnroutes2/master/chnroutes.txt",
    "domains": "https://raw.githubusercontent.com/felixonmars/dnsmasq-china-list/master/accelerated-domains.china.conf",
}
TAG_IP = "routeros-china-lists:ipv4"
TAG_DNS = "routeros-china-lists:domains"

def data_lines(text):
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if line and not line.startswith("#"):
            yield number, line

def parse_ipv4(text):
    networks = []
    for number, line in data_lines(text):
        try:
            network = ipaddress.ip_network(line, strict=True)
        except ValueError as error:
            raise ValueError(f"IPv4 source line {number}: invalid prefix") from error
        if network.version != 4 or not network.is_global or network.prefixlen == 0:
            raise ValueError(f"IPv4 source line {number}: expected a public IPv4 prefix")
        networks.append(network)
    if not networks:
        raise ValueError("Empty IPv4 list")
    return [str(network) for network in ipaddress.collapse_addresses(networks)]

def normalize_domain(domain):
    try:
        domain = domain.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise ValueError("Invalid domain") from error
    if not domain or len(domain) > 253:
        raise ValueError("Invalid domain length")
    for label in domain.split("."):
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label):
            raise ValueError(f"Invalid domain: {domain!r}")
    if re.fullmatch(r"[0-9.]+", domain):
        raise ValueError("An IP address is not a domain")
    return domain

def parse_domains(text):
    domains = set()
    for number, line in data_lines(text):
        if not line.startswith("server=/"):
            raise ValueError(f"Domain source line {number}: unexpected format")
        parts = line[len("server=/"):].split("/")
        if len(parts) < 2 or not parts[-1]:
            raise ValueError(f"Domain source line {number}: missing upstream")
        for domain in parts[:-1]:
            domains.add(normalize_domain(domain))
    if not domains:
        raise ValueError("Empty domain list")
    # Parent suffixes already cover child names when match-subdomain=yes.
    return sorted(domain for domain in domains
                  if not any(".".join(domain.split(".")[i:]) in domains
                             for i in range(1, len(domain.split(".")))))

def render(networks, domains):
    ip_lines = [
        "# Generated from misakaio/chnroutes2; data license CC-BY-SA-4.0",
        "/ip/firewall/address-list",
        f'remove [find where list="CN" comment="{TAG_IP}"]',
    ]
    ip_lines += [f'add list="CN" address="{network}" comment="{TAG_IP}"' for network in networks]
    dns_lines = [
        "# Generated from felixonmars/dnsmasq-china-list; source license WTFPL",
        "# No DNS address is specified. FWD uses the router default upstream.",
        "# Abort before changing entries if another tool owns an exact domain name.",
    ]
    for domain in domains:
        dns_lines.append(f':if ([:len [/ip/dns/static/find where name="{domain}" comment!="{TAG_DNS}"]] > 0) do={{ :error "DNS name conflict: {domain}" }}')
    dns_lines += ["/ip/dns/static", f'remove [find where comment="{TAG_DNS}"]']
    dns_lines += [f'add name="{domain}" type=FWD match-subdomain=yes comment="{TAG_DNS}"' for domain in domains]
    return {
        "cn-ipv4.txt": "\n".join(networks) + "\n",
        "china-domains.txt": "\n".join(domains) + "\n",
        "CN.rsc": "\n".join(ip_lines) + "\n",
        "china-domains.rsc": "\n".join(dns_lines) + "\n",
    }

def fetch(url):
    last_error = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "routeros-china-lists/1.0"})
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read(16 * 1024 * 1024 + 1)
            if len(data) > 16 * 1024 * 1024:
                raise ValueError("Source exceeds 16 MiB")
            return data.decode("utf-8-sig")
        except (OSError, UnicodeError, ValueError) as error:
            last_error = error
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise ValueError(f"Source download failed: {url}") from last_error

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip-file", type=Path, help="Local chnroutes source; otherwise download")
    parser.add_argument("--domain-file", type=Path, help="Local dnsmasq source; otherwise download")
    parser.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args()
    ip_text = args.ip_file.read_text(encoding="utf-8-sig") if args.ip_file else fetch(SOURCES["ipv4"])
    domain_text = args.domain_file.read_text(encoding="utf-8-sig") if args.domain_file else fetch(SOURCES["domains"])
    networks, domains = parse_ipv4(ip_text), parse_domains(domain_text)
    if not args.ip_file and len(networks) < 1000:
        raise ValueError("Downloaded IPv4 list unexpectedly small")
    if not args.domain_file and len(domains) < 1000:
        raise ValueError("Downloaded domain list unexpectedly small")
    manifest_path = args.output / "manifest.json"
    if manifest_path.exists() and not (args.ip_file or args.domain_file):
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))["counts"]
        for name, count in (("ipv4", len(networks)), ("domains", len(domains))):
            if count < previous[name] * 0.75:
                raise ValueError(f"{name} count fell more than 25%; keeping previous output")
    files = render(networks, domains)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": {"ipv4": len(networks), "domains": len(domains)},
        "sources": {key: {"url": SOURCES[key], "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
                    for key, text in (("ipv4", ip_text), ("domains", domain_text))},
        "domain_dns_address": None,
        "licenses": {"ipv4": "CC-BY-SA-4.0", "domains": "WTFPL"},
    }
    files["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    files["SHA256SUMS"] = "".join(f"{hashlib.sha256(content.encode('utf-8')).hexdigest()}  {name}\n"
                                for name, content in sorted(files.items()))
    # Validate all data before touching existing files. Git publishes all output in one commit.
    args.output.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        temp = args.output / (name + ".tmp")
        temp.write_bytes(content.encode("utf-8"))
        temp.replace(args.output / name)
    print(json.dumps({"counts": manifest["counts"], "output": str(args.output)}))

if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"Generation failed: {error}", file=sys.stderr)
        sys.exit(1)
