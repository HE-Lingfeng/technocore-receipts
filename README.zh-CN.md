# Technocore 导出记录核对工具

[![测试与包构建](https://github.com/HE-Lingfeng/technocore-receipts/actions/workflows/tests.yml/badge.svg?branch=codex%2Foffline-receipts&event=push)](https://github.com/HE-Lingfeng/technocore-receipts/actions/workflows/tests.yml)

这是独立的离线工具。它读取房间导出的 JSONL，核对 Ed25519 签名、nonce
重复或倒退、序号缺口和可选的文件哈希，输出 JSON 报告。

在项目目录运行，Python 3.10+，需要 `cryptography>=41`：

```sh
python3 -m technocore_receipts /导出文件的绝对路径.jsonl --room 房间名 > /报告的绝对路径.json
```

输入须是 `/r/房间名/export` 的原始导出，每行一个记录；普通房间接口返回的
`messages` 数组不能直接使用。记录、报告留在仓库外。

可通过 `--expected-did` 限定签名人，或通过 `--expected-sha256` 核对独立取得的
文件哈希。默认要求全部记录有签名；`--allow-unsigned` 允许缺少签名的旧记录，
但不能和指定签名人一起用。

运行演示和测试：

```sh
python3 examples/make_demo.py | python3 -m technocore_receipts - --room demo-room
python3 -m unittest discover -s tests -v
```

演示只在内存生成临时测试密钥，不读取你的身份、不向房间发帖、不付款。
报告不复制聊天正文，包含输入文件及各行哈希、验证计数、问题代码和核对范围。
正常返回 0；存在缺失签名或问题返回 1；参数、文件读取或输入大小错误返回 2。

## 自动验证

每次推送和提交 PR，GitHub Actions 都会分别用 Python 3.10 和 3.13 运行单元
测试、构建源码包与 wheel，并用 `twine check --strict` 检查包元数据和 README
渲染。随后在全新虚拟环境安装 wheel，从源码目录之外运行 CLI 合成演示。
点击上方状态徽章可查看各 Python 版本的结果与日志。

验签时，Ed25519 `did:key` 经 base58btc 解码得到 `0xed 0x01` 前缀及 32 字节
公钥；工具先核对、去掉前缀，再构造公钥。签名内容严格为 UTF-8 编码的
`房间名|nonce|正文`。字符串 nonce 保留原始数字，包括前导零；JSON 整数由
Python 精确解析，不经过浮点数，浮点 nonce 被拒绝。JavaScript 采集程序须在
普通 `JSON.parse` 将 19 位数字舍入之前保留其原始数字；舍入后再转字符串
无法恢复原值。

## 采集范围与连续性

`/export` 返回快照时仍保留的房间记录。房间按有限容量保留历史，覆盖时间会
随消息流量和大小变化，并非固定半小时；临时房间的过期记录也会被排除。

如果另写采集程序使用 `?since=S&format=json`，须注意：它从最新消息窗口中
筛选序号大于 S 的记录，并非从 S 开始向前分页。默认最多 50 条，最大 200 条。
例如上次看到第 100 条，房间已到第 300 条，默认查询可能只返回第 251–300 条。
单独核对这批记录，它们内部连续；只有同时提供第 100 条，工具才能看到
第 101–250 条的缺口。离线工具不知道采集程序的前一游标或预期结束序号。

采集程序应当：

1. 使用 `limit=200`，对每个非空响应核对首条序号等于 `S+1`，并检查后续序号
   连续；覆盖所需区间后再推进游标。空响应不证明之前历史完整，应保留原游标。
2. 出现缺口时尝试从 `/export` 补齐，按序号合并并保留原始记录字节；须核对
   首条接上 `S+1` 且到达预期结束序号。若缺失记录已经被清理，明确保留缺口，
   不能报告已恢复。
3. 记录房间 generation，发生变化时区分前后会话。同一 URL 反复读取时，
   按服务手册使用变化的 `n` 参数，避免拿到缓存响应。

最后一行完整的 JSONL 也可能只是截断文件的前半段。另行记录 HTTP 下载是否
完整结束；如果记录了房间最新序号，还要记录观察时间并与导出末尾比较。
两次读取属于不同快照，期间的新消息也可能造成差异。CLI 仅核对输入文件，
不会联网检查这些采集条件。

发布验证结果时，附上来源 URL、带时区的下载时间、generation（若有）、字节数、
SHA-256、首末序号及首末记录的 `ts`。序号和记录时间属于服务器元数据，
不受发送者签名认证。报告的 `coverage` 已含首末序号；时间和 HTTP 元数据
另写验证说明，涉及参与者数据的说明留在仓库外。公开示例见
[VALIDATION.md](VALIDATION.md)，游标问题的复现见
[#919](https://github.com/flop-labs/technocore-chat/issues/919)。

有效签名只证明对应公钥签署了该房间的文字和 nonce。序号、时间由服务赋值，
不在签名范围内；连续的导出也不证明房间完整历史。重复 nonce 是当前文件里的
观察结果，不是在复刻服务器的防重放缓存。交易结算、余额、排名及空投资格由
相应业务规则决定，本工具不作这类判断。

本项目独立于 Close Call 参赛程序，原参赛客户端仍按已有设置直接读取官方结果。
完整参数、报告字段与限制见 [英文说明](README.md)。
