# 生图服务配置

`scripts/imagegen.py` 调用任何 OpenAI 兼容的图片接口（`/images/generations` 文生图，`/images/edits` 带参考图）。

| 环境变量 | 作用 | 默认 |
|---|---|---|
| `AVS_IMAGE_BASE_URL` | 接口地址 | 京东内网 LLM 网关 `http://llm-gw.jd.local/v1` |
| `AVS_IMAGE_API_KEY` | 密钥（京东内网也可用 `JD_LLM_API_KEY`） | — |
| `AVS_IMAGE_MODELS` | 逗号分隔的模型链 | `GPT-Image-2.5-Flare-joybuilder,GPT-Image-2.5-Sunburst-joybuilder,GPT-image-2-joybuilder,Oxygen-Product-Pro,Oxygen-Imagen` |
| `AVS_IMAGE_PRIMARY_COUNT` | 链首几个算主模型 | 默认链 2；自定义链 1 |

降级规则（已实现并有测试）：主模型按顺序尝试；网络错误、超时只重试同一模型，**不降级**；只有全部主模型都返回额度、限流或鉴权类错误，才用后备模型，并在交付说明里写明。

京东外部使用示例：`AVS_IMAGE_BASE_URL=https://api.openai.com/v1`、`AVS_IMAGE_API_KEY=<key>`、`AVS_IMAGE_MODELS=gpt-image-1`。密钥只放环境变量，不写进项目文件。
