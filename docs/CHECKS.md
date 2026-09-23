# 本次公开检查

执行日期：2026-09-23；本地检查解释器：Python 3.11。

## 离线逻辑测试

命令：`python tools/run_public_tests.py`

结果：**262 项测试通过**。入口覆盖11个明确列出的测试模块，只运行不需要缺失资源的逻辑与源代码契约检查。它不是所有155份原有测试的全量运行，也不替代网易客户端验证。

## 快照检查

初次发布命令：`python tools/check_public_snapshot.py --verify-import`。后续贡献与CI使用不带该参数的命令，允许正常修改源码，不要求改动后的代码仍等于初始快照。

核对297个原样复制文件的SHA-256；检查公开目录文件类型、文件大小、Python 3源码语法和若干常见凭据/个人路径模式。三个Python 2 SDK适配层文件保留原样，不进行Python 3语法解析。扫描中的`C:/Users/test`是原有合成测试输入，已明确作为非个人路径处理。

模式检查通过不等于代码没有其他安全问题。此处没有作完整仓库漏洞审计。

后续图片提交的检查另覆盖439张PNG的签名、尺寸、哈希和许可署名清单，CI无需安装Pillow即可执行这些检查。

## 可选依赖审计

命令：`python -m pip_audit -r requirements-dev.txt -r requirements-tools.txt --format json`

使用pip-audit 2.10.1，依赖解析后返回 **No known vulnerabilities found**。结构化结果见[DEPENDENCY_AUDIT.json](DEPENDENCY_AUDIT.json)。这仅表示检查当时数据源未报告这些解析版本的已知漏洞，不是未来安全保证。

公开标准库测试入口不需要安装上述可选依赖。CI也只运行快照检查与标准库逻辑测试。
