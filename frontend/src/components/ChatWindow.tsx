import { ArrowRight, Braces, Image, Layers3, Sparkles, ShoppingBag, Wand2 } from 'lucide-react'
import type { Message } from '../types'
import { MessageBubble } from './MessageBubble'

type Props = {
  messages: Message[]
  draftContent: string
  draftModel?: string | null
  draftAgent?: string | null
  streaming: boolean
  onExampleClick: (text: string) => void
}

const examples = [
  { icon: <Braces size={18} />, title: '技术报错分析', text: '请解释这个 Python 报错，并给出排查步骤：NameError: name Field is not defined' },
  { icon: <ShoppingBag size={18} />, title: '电商文案优化', text: '帮我检查这段拼多多文案有没有风险词，并改得更适合转化：全网第一，永久去味，100%有效。' },
  { icon: <Image size={18} />, title: '图片提示词', text: '帮我写一段 Flux 生图提示词：蓝白清爽风格的智能体工作台产品海报。' },
  { icon: <Layers3 size={18} />, title: '多模型对比', text: '分别用多个模型回答：FastAPI 的 SSE 流式输出应该怎么设计？' },
]

export function ChatWindow({ messages, draftContent, draftModel, draftAgent, streaming, onExampleClick }: Props) {
  const draftMessage: Message | null = draftContent || streaming ? {
    id: 'draft-assistant',
    conversation_id: 'draft',
    role: 'assistant',
    content: draftContent || ' ',
    model: draftModel,
    agent_name: draftAgent || 'GeneralAgent',
    created_at: new Date().toISOString(),
  } : null

  if (messages.length === 0 && !draftMessage) {
    return (
      <div className="welcome">
        <div className="welcome__orb"><Sparkles size={32} /></div>
        <h2>构建你的多模型 Agent 工作台</h2>
        <p>这里不是普通聊天壳。你可以观察 Agent 执行过程、切换模型、保留会话历史，并逐步接入工具调用、多 Agent、图片生成和模型评测。</p>
        <div className="example-grid">
          {examples.map((item) => (
            <button key={item.title} type="button" onClick={() => onExampleClick(item.text)}>
              <span>{item.icon}</span>
              <strong>{item.title}</strong>
              <ArrowRight size={16} />
            </button>
          ))}
        </div>
        <div className="welcome__note"><Wand2 size={15} /> 推荐先测试 Day10：创建 AgentRun，然后通过 SSE 查看 token.delta。</div>
      </div>
    )
  }

  return (
    <div className="message-list">
      {messages.map((item) => <MessageBubble key={item.id} message={item} />)}
      {draftMessage ? <MessageBubble message={draftMessage} streaming={streaming} /> : null}
    </div>
  )
}
