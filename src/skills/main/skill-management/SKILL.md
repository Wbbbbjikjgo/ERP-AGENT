---
name: skill-management
description: 技能管理操作手册 - 下载、创建、测试、分配技能的完整流程
scope: main
version: 1.0.0
---

# 技能管理操作手册

## 概述
本技能定义了 Agent 管理技能库的标准操作流程，包括从外部下载技能、创建新技能、测试验证、以及分配给子Agent。

## 技能生命周期

### 1. 下载技能
```python
# 使用 download_skill.py 从URL下载技能包
python /skills/main/skill-management/download_skill.py --url <skill_zip_url> --target /skills/procurement/
```

**流程：**
1. 从指定URL下载 .zip 文件
2. 解压到目标目录
3. 验证 SKILL.md 存在且格式正确
4. 验证 frontmatter 包含必填字段（name, description, scope）

### 2. 创建技能
新技能必须包含：
- `SKILL.md` — 技能定义文件（含 YAML frontmatter）
- 可选的 Python 脚本（沙箱内执行）

**SKILL.md 格式：**
```markdown
---
name: skill-name
description: 一句话描述
scope: procurement|main
version: 1.0.0
---

# 技能标题

## 使用场景
...

## 操作步骤
...
```

### 3. 测试技能
在沙箱中执行技能附带的脚本，验证：
- 脚本无语法错误
- 依赖已安装
- 输出格式正确

### 4. 分配技能
使用 `assign_skill` 工具将技能分配给指定子Agent：
- 下载 → 创建 → 测试 → 分配 → 持久化到 StoreBackend

## 注意事项
- 技能文件存储在 `/persisted-skills/` 路径（StoreBackend）
- 本地技能源文件在 `src/skills/` 目录
- 沙箱内技能路径: `/skills/{scope}/{skill-name}/`
