# WeightLang package registry

这是 WeightLang 的 Git 包索引。索引只保存元数据；模型权重保存在各发布者的 GitHub Release 中。
需要包含注册表功能的源码版 `wgt`；旧版 Python wheel 不包含此客户端。

## 使用包

```sh
wgt add weightlang/gates
wgt add weightlang/gates --version v0.2.0
wgt update weightlang/gates
```

`add` 选择索引中最高的未撤回版本，随后固定精确版本、注册表 Git 提交、源码提交和制品哈希。
`wgt.toml` 保存完整来源路径，`wgt.sum` 保存完整锁定信息；请一起提交 Git。
源码仍使用完整制品路径，例如：

```wgt
import hidden from "github.com/WeightLang/WeightLang/packages/gates/xor_mlp" layer=hidden freeze
```

内置计算库使用 `import std/nn`（wgt 0.3），无需安装或注册。

## 提交包

先确保 `gh auth login` 已登录，且账号拥有源仓库写权限。源码和对应 tag 必须推送到 GitHub。

```sh
wgt package --version v0.1.0
# 按打包结果推送对应源码 commit 和 package tag 后：
wgt publish --index dist/wgt.index.json --name your-owner/model --license MIT --edition 0.3
```

命令上传稳定 Release assets（不占用工具链 Latest），验证远端文件，然后创建索引 PR。
普通用户自动使用 fork；有索引写权限的维护者也通过 PR 提交。不会自动合并。
如果制品已上传，但 PR 创建失败，用相同参数加 `--register-only` 重试。
`--dry-run` 不上传、不提交；`--no-register` 只发布制品。

已有包也可单独注册：

```sh
wgt register github.com/your-owner/repo/packages/model \
  --name your-owner/model --version v0.1.0 --license MIT --edition 0.3
```

`register --dry-run` 会联网校验制品并打印候选记录，但不创建 PR。
注册不会自动赋予商标、版权或许可。包名必须是小写 `owner/name`，命名空间必须对应源仓库 GitHub owner。

## 审核与信任

索引路径是 `packages/<owner>/<name>/<version>.json`，每个版本一条不可变记录。
维护者审核源仓库控制权、许可证与包描述，再运行：

```sh
python scripts/validate.py --base <base-commit> --verify-assets
```

自动检查不是身份认证；维护者必须独立确认 PR 作者拥有源仓库发布权限。
同名包不能迁移到另一个源模块。既有记录只允许把 `yanked` 从 false 改为 true；不改版本、哈希和来源。
撤回会阻止新的添加/升级，已有锁定项目仍能使用缓存或原 Release。
删除 Release 会影响重新下载；目前没有镜像、签名、传递依赖或短名源码 import。

客户端校验源码 tag、release index、每个制品文件的大小与 SHA256，以及完整制品布局。
索引审核工作流使用只读令牌；下载仅做哈希和声明式检查，不执行包代码。
