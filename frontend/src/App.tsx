import { useEffect, useState } from "react";
import "./App.css";

type ApiResponse<T> = {
  code: number;
  message: string;
  data: T | null;
};

type HealthData = {
  status: string;
  app: string;
  env: string;
  time: string;
};

type HealthResponse = ApiResponse<HealthData>;

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    fetch("http://127.0.0.1:8000/api/health")
      .then((response) => {
        if (!response.ok) {
          throw new Error(`请求失败：${response.status}`);
        }
        return response.json();
      })
      .then((data: HealthResponse) => {
        if (data.code !== 0) {
          throw new Error(data.message || "后端返回业务错误");
        }
        setHealth(data);
      })
      .catch((err: unknown) => {
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("未知错误");
        }
      });
  }, []);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="logo">OpenAgent Studio</div>

        <button className="new-chat-button">+ 新建会话</button>

        <div className="conversation-list">
          <div className="conversation-item active">Day 2 后端基础结构</div>
          <div className="conversation-item">后续会话示例</div>
        </div>
      </aside>

      <main className="chat-main">
        <header className="chat-header">
          <div>
            <h1>OpenAgent Studio</h1>
            <p>React + FastAPI + OpenAI Agents SDK 多模型智能体工作台</p>
          </div>

          <select className="model-selector" defaultValue="glm-5.1">
            <option value="glm-5.1">GLM-5.1</option>
            <option value="qwen">Qwen</option>
            <option value="minimax">MiniMax</option>
          </select>
        </header>

        <section className="message-list">
          <div className="message assistant">
            <div className="message-role">Assistant</div>
            <div className="message-content">
              Day 2 主要验证后端基础结构：配置、日志、统一响应、统一异常和路由拆分。
            </div>
          </div>

          <div className="message user">
            <div className="message-role">User</div>
            <div className="message-content">后端健康检查状态是什么？</div>
          </div>

          <div className="message assistant">
            <div className="message-role">System</div>
            <div className="message-content">
              {error && <span className="error-text">后端连接失败：{error}</span>}

              {!error && !health && <span>正在请求后端 /api/health ...</span>}

              {health && (
                <pre>{JSON.stringify(health, null, 2)}</pre>
              )}
            </div>
          </div>
        </section>

        <footer className="composer">
          <input
            disabled
            placeholder="Day 2 暂不实现发送消息，后面开始接聊天接口"
          />
          <button disabled>发送</button>
        </footer>
      </main>

      <aside className="debug-panel">
        <h2>执行过程</h2>
        <div className="timeline-item success">1. 前端启动成功</div>
        <div className="timeline-item success">2. 请求后端 /api/health</div>
        <div className={health ? "timeline-item success" : "timeline-item"}>
          3. 等待后端返回统一响应结构
        </div>
        <div className={health?.data ? "timeline-item success" : "timeline-item"}>
          4. 后端基础结构验证完成
        </div>
      </aside>
    </div>
  );
}

export default App;