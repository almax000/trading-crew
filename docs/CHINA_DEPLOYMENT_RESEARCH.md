# TradingCrew 中国部署方案研究报告

## 研究日期
2026-01-18

---

## 1. 当前架构网络延迟分析

### 1.1 现有部署架构

```
中国用户 → Railway (美国) → DeepSeek API (中国)
   [~200ms]      [~300ms]
```

### 1.2 延迟组成

| 环节 | 延迟 | 说明 |
|------|------|------|
| 用户 → Railway | ~150-250ms | 中美网络 RTT |
| Railway → DeepSeek | ~250-350ms | 美国回中国 |
| DeepSeek 处理 | 主导因素 | LLM 推理时间 |
| 每个 Token 传输 | ~50ms | 网络往返 |

### 1.3 关键发现

- **LLM 处理时间是绝对主导**：8分钟总耗时中，LLM 调用占 95%+
- **Token 流速受网络影响**：本地 20 token/s，跨境可能降至 10-15 token/s
- **首字节时间增加**：本地 4.4s，加上网络可能达 6-8s

---

## 2. 中国 PaaS 平台对比

### 2.1 免备案方案

| 平台 | 节点 | 月费用 | 特点 |
|------|------|--------|------|
| **Zeabur** | 香港 | ~¥35 | 免备案、中文界面、支持 Docker |
| **Sealos** | 香港/新加坡 | ~¥50 | K8s 原生、按量计费 |
| **Railway** | 美国 | ~$5 | 当前方案、延迟高 |

### 2.2 需备案方案

| 平台 | 费用 | 备案周期 | 适用场景 |
|------|------|----------|----------|
| 阿里云 | ~¥100/月 | 2-4周 | 正式商用 |
| 腾讯云 | ~¥100/月 | 2-4周 | 正式商用 |

### 2.3 推荐：Zeabur 香港节点

**优势**：
- 无需 ICP 备案
- 中文界面，操作简单
- 支持 Docker 部署
- 香港节点延迟低 (~30-50ms 到大陆)
- 价格合理 (~¥35/月起)

**部署方式**：
```bash
# 使用 Zeabur CLI
npm install -g zeabur
zeabur login
zeabur deploy
```

---

## 3. 微信小程序可行性

### 3.1 技术要求

| 要求 | 难度 | 说明 |
|------|------|------|
| 企业资质 | 高 | 需要企业营业执照 |
| HTTPS 域名 | 中 | 需要备案域名 |
| 算法备案 | 高 | 使用 AI 必须备案 |
| 审核周期 | 长 | 2-4周 |

### 3.2 算法备案要求

根据《互联网信息服务算法推荐管理规定》：
- 提供 AI 生成内容需要算法备案
- 备案周期 30 个工作日
- 需要提交算法原理说明

### 3.3 结论

**不推荐**：门槛过高，适合正式商业化后考虑。

---

## 4. 钉钉/飞书机器人方案

### 4.1 方案对比

| 平台 | 流式支持 | 打字机效果 | 开发难度 |
|------|----------|------------|----------|
| **钉钉** | 原生 Stream 模式 | AI 卡片支持 | 低 |
| **飞书** | Webhook | 需要自己实现 | 中 |

### 4.2 钉钉 Stream 模式详解

钉钉 2024 年推出的 Stream 模式天然支持流式输出：

```python
# 钉钉 Stream 模式示例
from dingtalk_stream import AckMessage
import dingtalk_stream

def on_event(event):
    # 接收消息
    user_message = event.data.get("text", {}).get("content", "")

    # 流式返回 AI 卡片
    card_instance_id = create_ai_card(event)

    for token in generate_tokens(user_message):
        # 逐字更新卡片内容
        update_card_content(card_instance_id, token)

    return AckMessage.STATUS_OK
```

**AI 卡片特性**：
- 原生打字机效果
- 支持 Markdown 渲染
- 自动滚动
- 移动端体验好

### 4.3 飞书机器人

飞书目前只支持 Webhook 模式，需要：
1. 接收消息后立即返回
2. 异步处理后发送新消息
3. 无法原生实现打字机效果

变通方案：
- 使用消息卡片 + 定时更新
- 用户体验不如钉钉流畅

### 4.4 推荐

**优先钉钉**：原生 Stream 模式 + AI 卡片是最佳方案。

---

## 5. 阿里云百炼 API vs DeepSeek 官方

### 5.1 关键指标对比

| 指标 | 阿里云百炼 | DeepSeek 官方 |
|------|------------|---------------|
| **可用性 SLA** | 98.6% | 42% (高峰期) |
| **并发限制** | 更高 | 经常排队 |
| **网络延迟** | 国内节点 ~10ms | 需要跨境 |
| **价格** | 略高 10-20% | 较低 |
| **稳定性** | 企业级 | 波动大 |

### 5.2 百炼 API 优势

1. **高可用性**：背靠阿里云基础设施
2. **国内节点**：无跨境延迟
3. **不受 DeepSeek 高峰影响**：独立配额
4. **企业支持**：有 SLA 保障

### 5.3 接入方式

```python
# 百炼 API 兼容 OpenAI SDK
from openai import OpenAI

client = OpenAI(
    api_key="your-bailian-api-key",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

response = client.chat.completions.create(
    model="deepseek-chat",  # 或 deepseek-reasoner
    messages=[{"role": "user", "content": "Hello"}],
    stream=True
)
```

### 5.4 价格对比 (每百万 token)

| 模型 | DeepSeek 官方 | 阿里云百炼 |
|------|---------------|------------|
| deepseek-chat | ¥1 | ¥1.2 |
| deepseek-reasoner | ¥4 | ¥4.8 |

价格差异约 20%，但稳定性提升显著。

---

## 6. 综合推荐方案

### 6.1 最优方案：Zeabur 香港 + 阿里云百炼

```
中国用户 → Zeabur (香港) → 阿里云百炼 API
   [~30ms]      [~10ms]
```

**预期效果**：
- 首字节时间：4-5s（接近本地）
- Token 流速：18-20 token/s
- 总延迟降低 60%+

### 6.2 成本估算

| 项目 | 月费用 |
|------|--------|
| Zeabur 香港 | ~¥35 |
| 阿里云百炼 API | 按量（约 ¥50-100） |
| **总计** | **¥85-135/月** |

### 6.3 迁移步骤

1. **注册 Zeabur**：https://zeabur.com
2. **申请百炼 API**：https://bailian.console.aliyun.com
3. **修改环境变量**：
   ```bash
   DEEPSEEK_API_KEY=your-bailian-key
   BACKEND_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
   ```
4. **部署到 Zeabur 香港节点**
5. **验证流式输出效果**

### 6.4 备选方案：钉钉机器人

如果用户群体主要使用钉钉：
1. 部署后端到 Zeabur
2. 创建钉钉 Stream 机器人
3. 使用 AI 卡片实现打字机效果

---

## 7. 总结

| 方案 | 适用场景 | 优先级 |
|------|----------|--------|
| Zeabur + 百炼 | Web 访问、通用 | ⭐⭐⭐⭐⭐ |
| 钉钉机器人 | 企业内部使用 | ⭐⭐⭐⭐ |
| 飞书机器人 | 已有飞书生态 | ⭐⭐⭐ |
| 微信小程序 | 正式商业化 | ⭐⭐ |

**核心结论**：
- 网络延迟可通过部署位置优化，但 LLM 处理时间是根本瓶颈
- Zeabur 香港 + 阿里云百炼是性价比最优解
- 钉钉 Stream 模式是最佳机器人方案

---

*报告生成于 2026-01-18*
