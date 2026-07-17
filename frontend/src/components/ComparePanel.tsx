import { AlertTriangle, CheckCircle2, Clock3, Crown, Loader2, Scale } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { CompareCandidate, JudgeReport } from '../types'
import { formatDuration } from '../utils/format'


type Props = {
  candidates: CompareCandidate[]
  judgeReport: JudgeReport | null
  running: boolean
}


export function ComparePanel({ candidates, judgeReport, running }: Props) {
  if (candidates.length === 0 && !running) return null

  const scoreByModel = new Map(
    (judgeReport?.scores || []).map((item) => [item.model_config_id, item]),
  )

  return (
    <section className="compare-panel">
      <div className="compare-panel__header">
        <div>
          <span className="eyebrow">Parallel Evaluation</span>
          <h3><Scale size={19} /> 多模型并发对比</h3>
        </div>
        <span className={running ? 'compare-status compare-status--live' : 'compare-status'}>
          {running ? <Loader2 className="spin" size={15} /> : <CheckCircle2 size={15} />}
          {running ? '对比运行中' : '对比已完成'}
        </span>
      </div>

      <div className="compare-grid">
        {candidates.map((candidate) => {
          const score = scoreByModel.get(candidate.model_config_id)
          const winner = judgeReport?.winner_model_config_id === candidate.model_config_id
          return (
            <article key={candidate.model_config_id} className={winner ? 'compare-card compare-card--winner' : 'compare-card'}>
              <header>
                <div>
                  <strong>{candidate.display_name}</strong>
                  <span>{candidate.model_id}</span>
                </div>
                {winner ? <span className="winner-chip"><Crown size={13} /> 推荐</span> : null}
              </header>

              <div className="compare-card__meta">
                <span><Clock3 size={13} /> {formatDuration(candidate.duration_ms ?? undefined)}</span>
                {score ? <span>Judge {score.total.toFixed(1)} / 50</span> : null}
              </div>

              {candidate.status === 'failed' ? (
                <div className="compare-error"><AlertTriangle size={17} /> {candidate.error_message || '模型调用失败'}</div>
              ) : candidate.output_text ? (
                <div className="markdown-body compare-answer">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{candidate.output_text}</ReactMarkdown>
                </div>
              ) : (
                <div className="compare-pending"><Loader2 className="spin" size={17} /> 正在等待模型回答…</div>
              )}
            </article>
          )
        })}
      </div>

      {judgeReport ? (
        <div className="judge-card">
          <div className="judge-card__title"><Crown size={18} /> Judge 推荐：{judgeReport.winner_display_name}</div>
          <p>{judgeReport.summary}</p>
          {judgeReport.fallback_used ? <span className="judge-card__fallback">本次使用规则降级评分</span> : null}
        </div>
      ) : null}
    </section>
  )
}
