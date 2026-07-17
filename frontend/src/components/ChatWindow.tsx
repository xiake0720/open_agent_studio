import { ArrowRight, Braces, Image, Layers3, Sparkles, ShoppingBag, Wand2 } from 'lucide-react'
import type { CompareCandidate, JudgeReport, Message } from '../types'
import { MessageBubble } from './MessageBubble'
import { ComparePanel } from './ComparePanel'

type Props = {
  messages: Message[]
  draftContent: string
  draftModel?: string | null
  draftAgent?: string | null
  streaming: boolean
  compareCandidates: CompareCandidate[]
  judgeReport: JudgeReport | null
  compareRunning: boolean
  onExampleClick: (text: string) => void
}

const examples = [
  { icon: <Braces size={18} />, title: '诊断技术问题', text: '分析这段代码存在的问题，并给出清晰的修复步骤。' },
  { icon: <ShoppingBag size={18} />, title: '优化商品内容', text: '优化这段商品介绍，使表达更清晰、更有说服力，并检查潜在风险。' },
  { icon: <Image size={18} />, title: '设计视觉方案', text: '为我的产品设计一套简洁、专业的视觉创意方案。' },
  { icon: <Layers3 size={18} />, title: '比较解决方案', text: '从多个角度分析这个问题，并比较不同解决方案的优缺点。' },
]

export function ChatWindow({ messages, draftContent, draftModel, draftAgent, streaming, compareCandidates, judgeReport, compareRunning, onExampleClick }: Props) {
  const draftMessage: Message | null = (draftContent || streaming) && compareCandidates.length === 0 ? {
    id: 'draft-assistant',
    conversation_id: 'draft',
    role: 'assistant',
    content: draftContent || ' ',
    model: draftModel,
    agent_name: draftAgent || 'GeneralAgent',
    created_at: new Date().toISOString(),
  } : null

  if (messages.length === 0 && !draftMessage && compareCandidates.length === 0) {
    return (
      <div className="welcome">
        <div className="welcome__orb"><Sparkles size={32} /></div>
        <h2>今天想完成什么？</h2>
        <p>选择适合的智能体与模型，开始一次专注、连续的协作。</p>
        <div className="example-grid">
          {examples.map((item) => (
            <button key={item.title} type="button" onClick={() => onExampleClick(item.text)}>
              <span>{item.icon}</span>
              <strong>{item.title}</strong>
              <ArrowRight size={16} />
            </button>
          ))}
        </div>
        <div className="welcome__note"><Wand2 size={15} /> 会话会自动保留上下文，你可以随时继续之前的工作。</div>
      </div>
    )
  }

  return (
    <div className="message-list">
      {messages.map((item) => <MessageBubble key={item.id} message={item} />)}
      {draftMessage ? <MessageBubble message={draftMessage} streaming={streaming} /> : null}
      <ComparePanel candidates={compareCandidates} judgeReport={judgeReport} running={compareRunning} />
    </div>
  )
}
