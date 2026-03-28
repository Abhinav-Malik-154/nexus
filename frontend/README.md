# Nexus Frontend — Production-Grade DeFi Risk Dashboard

Modern Next.js 16 dashboard for real-time DeFi protocol risk monitoring with ML-powered predictions.

## ⚡ Quick Start

```bash
npm install
npm run dev
# → http://localhost:3000
```

## 🏗️ Architecture

**Stack:** Next.js 16 • React 19 • TypeScript • TailwindCSS v4 • wagmi 3.5

- **Pages**: /, /intelligence, /risk-map, /protection, /alerts
- **Components**: UI primitives + dashboard components
- **Hooks**: Contract interactions + data fetching
- **Real Data**: DefiLlama API (live protocol data)

## ✅ Features

- Real data from DefiLlama (no fake metrics!)
- Real model metrics: F1=31.2%, Recall=70.8%
- Production-grade UI with loading/error states
- Responsive design (mobile-first)
- Type-safe throughout

## 📊 Model Metrics

- **Precision**: 20.5% (many false positives - intentional)
- **Recall**: 70.8% (catches most exploits)
- **F1**: 31.2%, **AUC**: 66.2%

Better to warn early than miss a real threat.

## 🚀 Run

```bash
npm run dev    # Development
npm run build  # Production build
npm start      # Production server
```

---

**v1.0** • Production Ready • Honest Metrics
