# RouterOS China Lists

自动下载、验证并转换中国大陆 IPv4 网段及适合国内 DNS 解析的域名，面向 RouterOS 7.x。
每天北京时间/新加坡时间约 **05:17** 由 GitHub Actions 更新（GitHub 调度可能延迟），也可在 Actions 页面手动运行。

## 下载

| 文件 | 用途 |
| --- | --- |
| [cn-ipv4.txt](dist/cn-ipv4.txt) | 每行一个国内 IPv4 CIDR |
| [china-domains.txt](dist/china-domains.txt) | 每行一个域名，**没有 DNS 地址、没有 server=/、没有其他后缀** |
| [CN.rsc](dist/CN.rsc) | RouterOS IPv4 地址列表，列表名 CN |
| [china-domains.rsc](dist/china-domains.rsc) | RouterOS DNS FWD 条目，**不设置 forward-to，不写死 DNS 上游** |
| [manifest.json](dist/manifest.json) | 更新时间、数量、来源与来源内容哈希 |
| [SHA256SUMS](dist/SHA256SUMS) | 生成文件的 SHA-256 校验值 |

直接下载地址：
- https://raw.githubusercontent.com/blackjack7125/routeros-china-lists/main/dist/CN.rsc
- https://raw.githubusercontent.com/blackjack7125/routeros-china-lists/main/dist/china-domains.txt
- https://raw.githubusercontent.com/blackjack7125/routeros-china-lists/main/dist/china-domains.rsc
- https://raw.githubusercontent.com/blackjack7125/routeros-china-lists/main/dist/cn-ipv4.txt

## 重要：域名不附 DNS 的含义

纯文本域名文件仅保存域名。RouterOS FWD 文件省略 forward-to，因而使用 RouterOS **默认 DNS 上游**。
如果你的 CHR 默认 DNS 是旁路由，直接导入 FWD 文件并不会让国内 DNS 查询绕过旁路由。
要做国内外 DNS 分流，必须在自己的路由器配置中给这些条目设置国内 DNS 地址或国内 forwarder；项目不会替你设置。
DNS 域名名单和 IP 地址名单是两个独立集合，并非精准的地理分类，也无法保证每次解析都返回国内 IP。

## RouterOS 导入

上传或 fetch 生成的 rsc 文件后，先检查内容，再导入。以 IPv4 为例：

```routeros
/tool/fetch url="https://raw.githubusercontent.com/blackjack7125/routeros-china-lists/main/dist/CN.rsc" dst-path="CN.rsc"
/import file-name=CN.rsc
```

更新只替换本项目 comment 标记的条目；不会修改路由、DHCP、默认 DNS、防火墙过滤规则、OpenClash 或 IPv6。
如果 CN 列表还有其他工具维护的条目，它们会保留。
DNS 文件导入前会检查与其他工具维护的同名静态条目冲突；命中时提前报错。
父域名包含子域名；已有宽泛正则规则、其他父域名规则仍需自行检查。
RouterOS import 不是事务：中途失败可能留下部分条目。首次导入建议先备份并在你的 RouterOS 版本上检查。
转换器和文件格式已经过自动测试，尚未在真实 CHR 上导入验证。

## 本地转换

Python 3.12，全部使用标准库，无需安装依赖：

```sh
python -B -m unittest discover -s tests -v
python convert.py
# 使用自己下载的源文件：
python convert.py --ip-file chnroutes.txt --domain-file accelerated-domains.china.conf --output dist
```

转换器严格验证 CIDR 和域名；去重、合并相邻 IPv4 网段，移除父域名已覆盖的子域名。
下载失败、解析错误、远程名单不足 1000 条或数量比上次下降超过 25% 时不发布新数据。
在线任务两份源文件均验证成功后再生成、提交；发布以 Git 提交为边界。

## 来源与许可

本项目不是 MikroTik 官方名单，转换代码为 MIT 许可（见 LICENSE）。
生成数据保留各自来源许可：
- IPv4：[misakaio/chnroutes2](https://github.com/misakaio/chnroutes2)，CC BY-SA 4.0。转换包括去重和网段聚合。许可：https://creativecommons.org/licenses/by-sa/4.0/
- 域名：[felixonmars/dnsmasq-china-list](https://github.com/felixonmars/dnsmasq-china-list)，WTFPL。转换包括提取域名、IDNA 归一化、去重和父域名合并。许可：https://www.wtfpl.net/txt/copying/

生成文件随附 manifest 来源及许可信息。使用或再分发名单时请遵守上游许可。
