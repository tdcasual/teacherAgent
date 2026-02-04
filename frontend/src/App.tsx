import { useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function App() {
  const [mode, setMode] = useState<'student' | 'teacher'>('student')

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">Physics Helper</div>
        <div className="segmented">
          <button className={mode === 'student' ? 'active' : ''} onClick={() => setMode('student')}>学生</button>
          <button className={mode === 'teacher' ? 'active' : ''} onClick={() => setMode('teacher')}>老师</button>
        </div>
      </header>

      <main className="content">
        {mode === 'student' ? (
          <section className="card">
            <h2>学生入口</h2>
            <p>上传作业图片、查看反馈、进行学习讨论。</p>
            <div className="actions">
              <button>拍照上传</button>
              <button>开始对话</button>
              <button>查看作业</button>
            </div>
          </section>
        ) : (
          <section className="card">
            <h2>老师入口</h2>
            <p>课堂材料采集、课后诊断与作业生成、核心例题管理。</p>
            <div className="actions">
              <button>课堂采集</button>
              <button>课后诊断</button>
              <button>核心例题</button>
            </div>
          </section>
        )}

        <section className="card api">
          <h3>服务状态</h3>
          <p>API: {API_URL}</p>
          <p>适配移动端的简洁界面已启用。</p>
        </section>
      </main>
    </div>
  )
}
