# 原创20秒音色与长音练习

这里的MIDI与配方为原创CC0材料，不包含原版Minecraft音频或第三方采样。主旋律61–82、统一根音72，适合检查整句保持一个音色而非逐音切换。

用`python run_pipeline.py timbre-study NEW_DIR`生成完整练习：三种音体方向、同增益独奏/混合、25格变速校准，以及同样本自然衰减/补触发对照。单音可用`design-timbre vowel_recipe.json --out NEW_DIR`，palette可用`build-palette palette_spec.json --out NEW_DIR`。

上述native方向缺省为原创MC-inspired，不能当作原版音符盒样本。要比较原版或自己的录音，按[声音教程](../../skills/sound-designer/references/guide.md)在recipe中明确提供本地单音路径、根音和来源权利。工具不自动寻找用户游戏或旧作品。

本例不是专业编曲能力或实际游戏音效的验收。听清音色、持续与重触发代价后，再对具体用户曲目制作候选。
