'use client'

import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'
import { useProtocolCount, useHighRiskProtocols, useAlertThreshold, getRiskColor, getRiskLevel } from '@/hooks/useNexus'

// Protocol dependency graph data
const PROTOCOLS = [
  { id: 'Lido', category: 'Liquid Staking', tvl: 32.5 },
  { id: 'Aave V3', category: 'Lending', tvl: 11.2 },
  { id: 'EigenLayer', category: 'Restaking', tvl: 15.8 },
  { id: 'ether.fi', category: 'Liquid Staking', tvl: 6.4 },
  { id: 'Ethena', category: 'Basis Trading', tvl: 5.2 },
  { id: 'Uniswap V3', category: 'DEX', tvl: 5.1 },
  { id: 'Maker', category: 'CDP', tvl: 4.8 },
  { id: 'Pendle', category: 'Yield', tvl: 4.2 },
  { id: 'Compound V3', category: 'Lending', tvl: 2.1 },
  { id: 'Morpho', category: 'Lending', tvl: 1.8 },
]

const LINKS = [
  { source: 'Lido', target: 'Aave V3', type: 'collateral' },
  { source: 'Lido', target: 'EigenLayer', type: 'restaking' },
  { source: 'ether.fi', target: 'EigenLayer', type: 'restaking' },
  { source: 'Ethena', target: 'Aave V3', type: 'hedging' },
  { source: 'Maker', target: 'Aave V3', type: 'liquidation' },
  { source: 'Compound V3', target: 'Aave V3', type: 'oracle' },
  { source: 'Morpho', target: 'Aave V3', type: 'optimization' },
  { source: 'Uniswap V3', target: 'Aave V3', type: 'liquidation' },
  { source: 'Pendle', target: 'Lido', type: 'yield' },
  { source: 'Pendle', target: 'ether.fi', type: 'yield' },
]

// Simulated risk scores (in production, fetch from oracle)
const MOCK_SCORES: Record<string, number> = {
  'Lido': 15,
  'Aave V3': 22,
  'EigenLayer': 35,
  'ether.fi': 28,
  'Ethena': 72, // High risk
  'Uniswap V3': 12,
  'Maker': 18,
  'Pendle': 45,
  'Compound V3': 20,
  'Morpho': 25,
}

interface NodeData {
  id: string
  category: string
  tvl: number
  score: number
  x?: number
  y?: number
  fx?: number | null
  fy?: number | null
}

interface LinkData {
  source: string | NodeData
  target: string | NodeData
  type: string
}

export default function RiskMapPage() {
  const svgRef = useRef<SVGSVGElement>(null)
  const [selectedNode, setSelectedNode] = useState<NodeData | null>(null)
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)

  const { data: protocolCount } = useProtocolCount()
  const { data: highRiskProtocols } = useHighRiskProtocols()
  const { data: alertThreshold } = useAlertThreshold()

  useEffect(() => {
    if (!svgRef.current) return

    const width = 900
    const height = 600

    // Clear previous
    d3.select(svgRef.current).selectAll('*').remove()

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', [0, 0, width, height])

    // Add defs for gradients and arrows
    const defs = svg.append('defs')

    // Arrow marker
    defs.append('marker')
      .attr('id', 'arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 25)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('fill', '#374151')
      .attr('d', 'M0,-5L10,0L0,5')

    // Prepare data
    const nodes: NodeData[] = PROTOCOLS.map(p => ({
      ...p,
      score: MOCK_SCORES[p.id] ?? 0,
    }))

    const links: LinkData[] = LINKS.map(l => ({ ...l }))

    // Force simulation
    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink<NodeData, LinkData>(links).id(d => d.id).distance(120))
      .force('charge', d3.forceManyBody().strength(-400))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(50))

    // Links
    const link = svg.append('g')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', '#374151')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', 1.5)
      .attr('marker-end', 'url(#arrow)')

    // Node groups
    const node = svg.append('g')
      .selectAll('g')
      .data(nodes)
      .join('g')
      .style('cursor', 'pointer')
      .call(d3.drag<SVGGElement, NodeData>()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart()
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (event, d) => {
          d.fx = event.x
          d.fy = event.y
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0)
          d.fx = null
          d.fy = null
        }) as any)

    // Node circles
    node.append('circle')
      .attr('r', d => 15 + d.tvl / 3)
      .attr('fill', d => getRiskColor(d.score))
      .attr('stroke', '#1a1a2e')
      .attr('stroke-width', 2)
      .on('mouseenter', (_, d) => setHoveredNode(d.id))
      .on('mouseleave', () => setHoveredNode(null))
      .on('click', (_, d) => setSelectedNode(d))

    // Node labels
    node.append('text')
      .text(d => d.id)
      .attr('text-anchor', 'middle')
      .attr('dy', d => 25 + d.tvl / 3)
      .attr('fill', '#e2e8f0')
      .attr('font-size', '11px')
      .attr('font-family', 'monospace')

    // Risk score labels
    node.append('text')
      .text(d => d.score)
      .attr('text-anchor', 'middle')
      .attr('dy', 4)
      .attr('fill', '#0a0a0a')
      .attr('font-size', '10px')
      .attr('font-weight', 'bold')
      .attr('font-family', 'monospace')

    // Update positions
    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as NodeData).x!)
        .attr('y1', d => (d.source as NodeData).y!)
        .attr('x2', d => (d.target as NodeData).x!)
        .attr('y2', d => (d.target as NodeData).y!)

      node.attr('transform', d => `translate(${d.x},${d.y})`)
    })

    return () => { simulation.stop() }
  }, [])

  return (
    <div style={{ minHeight: 'calc(100vh - 48px)', background: '#0a0a0a', padding: '80px 24px' }}>
      <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
        {/* Header */}
        <div style={{ marginBottom: '32px' }}>
          <div style={{ color: '#00ff9d', fontFamily: 'monospace', fontSize: '14px', marginBottom: '8px' }}>
            {'>'} NEXUS RISK MAP
          </div>
          <h1 style={{ fontFamily: 'monospace', fontSize: '36px', color: '#e2e8f0', margin: 0 }}>
            Protocol Contagion Graph
          </h1>
          <p style={{ color: '#64748b', fontFamily: 'monospace', fontSize: '13px', marginTop: '8px' }}>
            // Real-time visualization of DeFi protocol dependencies and risk propagation
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: '24px' }}>
          {/* Graph */}
          <div style={{ background: '#0f0f0f', border: '1px solid #1a1a2e', padding: '16px' }}>
            <svg ref={svgRef} style={{ width: '100%', height: '600px' }} />
          </div>

          {/* Sidebar */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Stats */}
            <div style={{ background: '#0f0f0f', border: '1px solid #1a1a2e', padding: '16px' }}>
              <div style={{ color: '#64748b', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.15em', marginBottom: '12px' }}>
                SYSTEM STATUS
              </div>
              {[
                { label: 'Protocols', value: protocolCount?.toString() ?? '10', color: '#00ff9d' },
                { label: 'High Risk', value: highRiskProtocols?.length?.toString() ?? '1', color: '#ef4444' },
                { label: 'Threshold', value: alertThreshold?.toString() ?? '70', color: '#f59e0b' },
              ].map(s => (
                <div key={s.label} style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'monospace', fontSize: '12px', marginBottom: '8px' }}>
                  <span style={{ color: '#64748b' }}>{s.label}</span>
                  <span style={{ color: s.color }}>{s.value}</span>
                </div>
              ))}
            </div>

            {/* Legend */}
            <div style={{ background: '#0f0f0f', border: '1px solid #1a1a2e', padding: '16px' }}>
              <div style={{ color: '#64748b', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.15em', marginBottom: '12px' }}>
                RISK LEVELS
              </div>
              {[
                { level: 'LOW', range: '0-49', color: '#00ff9d' },
                { level: 'MEDIUM', range: '50-69', color: '#eab308' },
                { level: 'HIGH', range: '70-79', color: '#f59e0b' },
                { level: 'CRITICAL', range: '80-100', color: '#ef4444' },
              ].map(l => (
                <div key={l.level} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: l.color }} />
                  <span style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '11px', flex: 1 }}>{l.level}</span>
                  <span style={{ color: '#64748b', fontFamily: 'monospace', fontSize: '11px' }}>{l.range}</span>
                </div>
              ))}
            </div>

            {/* Selected Protocol */}
            {selectedNode && (
              <div style={{ background: '#0f0f0f', border: '1px solid #1a1a2e', padding: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <div style={{ color: '#64748b', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.15em' }}>
                    SELECTED
                  </div>
                  <button
                    onClick={() => setSelectedNode(null)}
                    style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: '14px' }}
                  >
                    ×
                  </button>
                </div>
                <div style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '16px', fontWeight: 'bold', marginBottom: '8px' }}>
                  {selectedNode.id}
                </div>
                <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
                  <span style={{
                    color: getRiskColor(selectedNode.score),
                    background: `${getRiskColor(selectedNode.score)}15`,
                    border: `1px solid ${getRiskColor(selectedNode.score)}30`,
                    padding: '2px 8px',
                    fontSize: '9px',
                    textTransform: 'uppercase',
                    letterSpacing: '0.1em',
                    fontFamily: 'monospace',
                  }}>
                    {getRiskLevel(selectedNode.score)}
                  </span>
                  <span style={{
                    color: '#06b6d4',
                    background: '#06b6d415',
                    border: '1px solid #06b6d430',
                    padding: '2px 8px',
                    fontSize: '9px',
                    textTransform: 'uppercase',
                    letterSpacing: '0.1em',
                    fontFamily: 'monospace',
                  }}>
                    {selectedNode.category}
                  </span>
                </div>
                {[
                  { label: 'Risk Score', value: selectedNode.score.toString() },
                  { label: 'TVL', value: `$${selectedNode.tvl}B` },
                  { label: 'Category', value: selectedNode.category },
                ].map(r => (
                  <div key={r.label} style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'monospace', fontSize: '12px', marginBottom: '6px' }}>
                    <span style={{ color: '#64748b' }}>{r.label}</span>
                    <span style={{ color: '#e2e8f0' }}>{r.value}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Link Types */}
            <div style={{ background: '#0f0f0f', border: '1px solid #1a1a2e', padding: '16px' }}>
              <div style={{ color: '#64748b', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.15em', marginBottom: '12px' }}>
                DEPENDENCY TYPES
              </div>
              {['collateral', 'restaking', 'hedging', 'liquidation', 'oracle', 'yield'].map(t => (
                <div key={t} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                  <div style={{ width: '20px', height: '2px', background: '#374151' }} />
                  <span style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '11px', textTransform: 'capitalize' }}>{t}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
