# Technocore 导出记录核对工具

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

有效签名只证明对应公钥签署了该房间的文字和 nonce。序号、时间由服务赋值，
不在签名范围内；连续的导出也不证明房间完整历史。重复 nonce 是当前文件里的
观察结果，不是在复刻服务器的防重放缓存。交易结算、余额、排名及空投资格由
相应业务规则决定，本工具不作这类判断。

本项目独立于 Close Call 参赛程序，原参赛客户端仍按已有设置直接读取官方结果。
完整参数、报告字段与限制见 [英文说明](README.md)。
