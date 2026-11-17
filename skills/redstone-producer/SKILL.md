---
name: redstone-producer
description: 从用户需求或中断项目组织红石音乐生产，制定路线、分配专业工作、处理反馈并维护可验证交接。用于作品主控，不替代具体音乐或模组操作。
---

# 红石音乐主控

把用户需求转成可听、可玩的作品。默认自主推进，代表样段和最终成品请用户听看；常规可逆操作与修复不逐步请示。

先读项目brief、`project.json`、`state.json`与`handoff`，再决定当前缺口。新项目先查真实素材与`capabilities --probe`；没有MIDI时按音乐任务组织制作，不凭空标记完成。

职责边界与[项目方法](references/guide.md)在这里。跨层操作遵守[工作流](../../docs/WORKFLOW.md)：母版、声音改编、机器、视觉和成片分别认可。

- 音乐问题路由到[music-director](../music-director/SKILL.md)。
- 音符盒表达与声音问题分别路由到[noteblock-arranger](../noteblock-arranger/SKILL.md)、[sound-designer](../sound-designer/SKILL.md)。
- 实体机制、场景与演出按各自Skill处理；没有子agent时自己按相同合同顺序完成。
- 把每个专业任务限定到相关输入、明确目标、允许输出和版本前提。专业产物由主控集成，独立工具重新验证。

每轮交付候选、差异和证据。记录为什么选择及仍不确定的事实；同因失败两次后提出新的有依据路线。不要把更多轨道、更多粒子或更大世界当成质量提升。

完成时`handoff`应说明最新认可版本、当前问题、下一操作、失败路线与实际验证范围。项目完成需要合同中的必选交付与用户最终听看，不从技术pass推断艺术认可。
