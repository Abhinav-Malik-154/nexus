'use client'

import Link from 'next/link'
import { useProtocolCount, useHighRiskProtocols, useAlertThreshold } from '@/hooks/useNexus'

export default function Home() {
  const { data: protocolCount } = useProtocolCount()
  const { data: highRiskProtocols } = useHighRiskProtocols()
  const { data: alertThreshold } = useAlertThreshold()

  return (
    <div className="page-container">
      <div className="max-w-container">
        {/* Terminal Header */}
        <div className="terminal-line">
          {'>'} NEXUS v1.0.0 — DEFI CONTAGION INTELLIGENCE SYSTEM
          <span className="cursor-blink">_</span>
        </div>

        {/* Hero */}
        <h1 className="hero-title">
          <span className="text-light">PREDICT.</span>
          <br />
          <span className="text-accent">PROTECT.</span>
          <br />
          <span className="text-light">SURVIVE DEFI.</span>
        </h1>

        {/* Description */}
        <div className="comment-lines">
          <div>// AI-powered contagion prediction for DeFi protocols</div>
          <div>// Autonomous protection. Real-time risk. On-chain execution.</div>
        </div>

        {/* System Status */}
        <div className="card status-card">
          <div className="status-header">
            <span className="live-dot" />
            <span className="status-label">SYSTEM STATUS</span>
          </div>
          <div className="status-grid">
            {[
              { label: '[PROTOCOLS]', value: protocolCount?.toString() ?? '10', color: '#06b6d4' },
              { label: '[MODEL]', value: 'GNN — ACTIVE', color: '#00ff9d' },
              { label: '[THRESHOLD]', value: alertThreshold?.toString() ?? '70', color: '#f59e0b' },
              { label: '[HIGH RISK]', value: highRiskProtocols?.length?.toString() ?? '0', color: highRiskProtocols?.length ? '#ef4444' : '#00ff9d' },
            ].map((row) => (
              <div key={row.label} className="status-row">
                <span className="status-key">{row.label}</span>
                <span style={{ color: row.color }}>{row.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* CTA Buttons */}
        <div className="button-group">
          <Link href="/risk-map" className="btn btn-primary">
            ▶ OPEN RISK MAP
          </Link>
          <Link href="/protection" className="btn btn-outline">
            ◈ PROTECTION VAULT
          </Link>
        </div>

        {/* Stats */}
        <div className="stats-grid">
          {[
            { label: 'TVL MONITORED', value: '$149B+' },
            { label: 'PROTOCOLS', value: '7,213' },
            { label: 'EXPLOITS DATA', value: '8' },
            { label: 'MODEL ACCURACY', value: '71%' },
          ].map((stat) => (
            <div key={stat.label} className="stat-card">
              <div className="stat-label">{stat.label}</div>
              <div className="stat-value">{stat.value}</div>
            </div>
          ))}
        </div>

        {/* Features */}
        <div className="features-grid">
          {[
            {
              title: 'RISK ORACLE',
              desc: 'AI-generated risk scores updated on-chain every 15 minutes via authorized backend',
              tag: 'AI POWERED',
              color: '#00ff9d',
            },
            {
              title: 'CONTAGION GRAPH',
              desc: 'Protocol dependency visualization showing real-time risk propagation paths',
              tag: 'LIVE DATA',
              color: '#06b6d4',
            },
            {
              title: 'AUTO PROTECTION',
              desc: 'Chainlink Automation triggers autonomous fund transfers when thresholds crossed',
              tag: 'ON-CHAIN',
              color: '#7c3aed',
            },
            {
              title: 'GNN MODEL',
              desc: 'Graph Neural Network trained on historical exploit data for contagion prediction',
              tag: 'PYTORCH',
              color: '#f59e0b',
            },
          ].map((card) => (
            <div key={card.title} className="feature-card">
              <div className="feature-header">
                <span className="feature-title">{card.title}</span>
                <span className="feature-tag" style={{ color: card.color, borderColor: `${card.color}30`, background: `${card.color}15` }}>
                  {card.tag}
                </span>
              </div>
              <div className="feature-desc">{card.desc}</div>
            </div>
          ))}
        </div>

        {/* Pipeline */}
        <div className="card pipeline-card">
          <div className="pipeline-label">· NEXUS PIPELINE</div>
          <div className="pipeline-steps">
            {[
              { step: 'FETCH DATA', active: false },
              { step: 'BUILD GRAPH', active: false },
              { step: 'RUN GNN', active: false },
              { step: 'UPDATE ORACLE', active: false },
              { step: 'TRIGGER PROTECTION', active: true },
            ].map((item, i) => (
              <div key={item.step} className="pipeline-item">
                <span className={`pipeline-step ${item.active ? 'active' : ''}`}>
                  {item.step}
                </span>
                {i < 4 && <span className="pipeline-arrow">→</span>}
              </div>
            ))}
          </div>
        </div>

        {/* Tech Stack */}
        <div className="card tech-card">
          <div className="tech-label">· TECH STACK</div>
          <div className="tech-grid">
            {[
              { name: 'Solidity', desc: 'Smart Contracts' },
              { name: 'Foundry', desc: 'Testing & Deploy' },
              { name: 'PyTorch', desc: 'GNN Model' },
              { name: 'Next.js', desc: 'Frontend' },
              { name: 'Chainlink', desc: 'Automation' },
              { name: 'wagmi', desc: 'Web3 Hooks' },
            ].map((tech) => (
              <div key={tech.name} className="tech-item">
                <span className="tech-name">{tech.name}</span>
                <span className="tech-desc">{tech.desc}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <style jsx>{`
        .page-container {
          min-height: calc(100vh - 48px);
          background: #0a0a0a;
          background-image: radial-gradient(ellipse at 50% 20%, rgba(124,58,237,0.08) 0%, transparent 60%);
          padding: 80px 24px;
        }
        .max-w-container {
          max-width: 1200px;
          margin: 0 auto;
        }
        .terminal-line {
          color: #00ff9d;
          font-family: monospace;
          font-size: 14px;
          margin-bottom: 32px;
        }
        .hero-title {
          font-family: monospace;
          font-weight: bold;
          font-size: clamp(40px, 8vw, 72px);
          line-height: 1.1;
          margin: 0 0 24px 0;
        }
        .text-light { color: #e2e8f0; }
        .text-accent { color: #00ff9d; }
        .comment-lines {
          color: #64748b;
          font-family: monospace;
          font-size: 14px;
          margin-bottom: 40px;
        }
        .card {
          background: #0f0f0f;
          border: 1px solid #1a1a2e;
          padding: 20px;
          margin-bottom: 24px;
        }
        .status-card { max-width: 400px; }
        .status-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 16px;
        }
        .live-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #00ff9d;
          animation: pulse 2s infinite;
        }
        .status-label {
          color: #00ff9d;
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 0.15em;
        }
        .status-row {
          display: flex;
          gap: 16px;
          font-family: monospace;
          font-size: 13px;
          margin-bottom: 8px;
        }
        .status-key {
          color: #64748b;
          width: 120px;
        }
        .button-group {
          display: flex;
          gap: 16px;
          margin-bottom: 48px;
        }
        .btn {
          padding: 12px 24px;
          font-family: monospace;
          font-size: 12px;
          font-weight: bold;
          text-transform: uppercase;
          letter-spacing: 0.1em;
          text-decoration: none;
          cursor: pointer;
        }
        .btn-primary {
          background: #f59e0b;
          color: #0a0a0a;
          border: none;
        }
        .btn-outline {
          background: transparent;
          color: #00ff9d;
          border: 1px solid #00ff9d;
        }
        .stats-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 16px;
          margin-bottom: 48px;
        }
        .stat-card {
          background: #0f0f0f;
          border: 1px solid #1a1a2e;
          padding: 20px;
        }
        .stat-label {
          color: #64748b;
          font-size: 10px;
          text-transform: uppercase;
          letter-spacing: 0.15em;
          margin-bottom: 8px;
        }
        .stat-value {
          color: #00ff9d;
          font-size: 28px;
          font-weight: bold;
          font-family: monospace;
        }
        .features-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 16px;
          margin-bottom: 24px;
        }
        .feature-card {
          background: #0f0f0f;
          border: 1px solid #1a1a2e;
          padding: 24px;
        }
        .feature-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 12px;
        }
        .feature-title {
          color: #e2e8f0;
          font-size: 14px;
          font-weight: bold;
          letter-spacing: 0.1em;
        }
        .feature-tag {
          padding: 2px 8px;
          font-size: 9px;
          text-transform: uppercase;
          letter-spacing: 0.1em;
          border: 1px solid;
          font-family: monospace;
        }
        .feature-desc {
          color: #64748b;
          font-size: 13px;
          line-height: 1.5;
        }
        .pipeline-card, .tech-card { padding: 24px; }
        .pipeline-label, .tech-label {
          color: #64748b;
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 0.15em;
          margin-bottom: 20px;
        }
        .pipeline-steps {
          display: flex;
          align-items: center;
          gap: 12px;
          font-family: monospace;
          font-size: 12px;
          flex-wrap: wrap;
        }
        .pipeline-item {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .pipeline-step {
          color: #64748b;
          border: 1px solid #1a1a2e;
          padding: 6px 12px;
          background: transparent;
        }
        .pipeline-step.active {
          color: #f59e0b;
          background: rgba(245, 158, 11, 0.1);
          border-color: rgba(245, 158, 11, 0.3);
        }
        .pipeline-arrow { color: #64748b; }
        .tech-grid {
          display: grid;
          grid-template-columns: repeat(6, 1fr);
          gap: 16px;
        }
        .tech-item {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .tech-name {
          color: #e2e8f0;
          font-family: monospace;
          font-size: 13px;
          font-weight: bold;
        }
        .tech-desc {
          color: #64748b;
          font-size: 10px;
        }
        @media (max-width: 768px) {
          .stats-grid, .features-grid { grid-template-columns: 1fr; }
          .tech-grid { grid-template-columns: repeat(3, 1fr); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  )
}
