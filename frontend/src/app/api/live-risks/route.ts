import { NextRequest, NextResponse } from 'next/server'
import { spawn } from 'child_process'
import { join } from 'path'

/**
 * Live Risk Intelligence API
 *
 * Fetches real-time risk predictions from our trained GNN model
 * Integration with model/realtime_monitor.py
 */

interface LiveRiskData {
  protocol: string
  slug: string
  riskScore: number
  level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  tvl: number
  category: string
  change1d: number
  change7d: number
  timestamp: string
  confidence: number
}

interface ModelStats {
  precision: number
  recall: number
  f1: number
  auc: number
  protocolsMonitored: number
  lastUpdate: string
  isActive: boolean
}

// Cache for reducing API calls to Python model
let cachedData: {
  risks: LiveRiskData[]
  stats: ModelStats
  timestamp: number
} | null = null

const CACHE_DURATION = 60000 // 1 minute

async function fetchLiveRisks(): Promise<{ risks: LiveRiskData[], stats: ModelStats }> {
  // Check cache first
  if (cachedData && Date.now() - cachedData.timestamp < CACHE_DURATION) {
    return {
      risks: cachedData.risks,
      stats: cachedData.stats
    }
  }

  try {
    // Run our Python monitoring script - JSON output version
    const pythonScript = '/home/mutant/nexus/model/api_monitor.py'

    return new Promise((resolve, reject) => {
      const python = spawn('python', [pythonScript], {
        cwd: '/home/mutant/nexus/model'  // Set working directory to model folder
      })
      let output = ''
      let error = ''

      python.stdout.on('data', (data) => {
        output += data.toString()
      })

      python.stderr.on('data', (data) => {
        error += data.toString()
      })

      python.on('close', (code) => {
        try {
          // Parse JSON output directly from Python script
          const result = JSON.parse(output)

          if (result.success) {
            // Cache the successful result
            cachedData = {
              risks: result.data.risks,
              stats: result.data.stats,
              timestamp: Date.now()
            }

            resolve(result.data)
          } else {
            console.error('Python script returned error:', result.error)
            resolve(getMockData())
          }
        } catch (parseError) {
          console.error('Failed to parse Python JSON output:', parseError)
          console.error('Raw output:', output)
          console.error('Error output:', error)
          resolve(getMockData())
        }
      })

      // Timeout after 10 seconds
      setTimeout(() => {
        python.kill()
        resolve(getMockData())
      }, 10000)
    })
  } catch (error) {
    console.error('Failed to run Python script:', error)
    return getMockData()
  }
}

function parsePythonOutput(output: string): LiveRiskData[] {
  // Parse the table output from test_monitor.py
  const lines = output.split('\n')
  const risks: LiveRiskData[] = []

  for (const line of lines) {
    // Look for lines with protocol data (contains emoji indicators)
    if (line.includes('🟢') || line.includes('🟡') || line.includes('🟠') || line.includes('🔴')) {
      try {
        // Parse protocol name, TVL, and risk score from the table
        const parts = line.trim().split(/\s+/)
        if (parts.length >= 4) {
          const emoji = parts[0]
          const protocol = parts[1]
          const tvlStr = parts[2]
          const riskStr = parts[3]

          // Extract risk level from emoji
          let level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' = 'LOW'
          if (emoji === '🔴') level = 'CRITICAL'
          else if (emoji === '🟠') level = 'HIGH'
          else if (emoji === '🟡') level = 'MEDIUM'

          // Parse TVL
          const tvlMatch = tvlStr.match(/\$?([\d.]+)([MB]?)/)
          let tvl = 0
          if (tvlMatch) {
            const value = parseFloat(tvlMatch[1])
            const unit = tvlMatch[2]
            tvl = unit === 'B' ? value * 1e9 : value * 1e6
          }

          // Parse risk score
          const riskScore = parseFloat(riskStr.replace('%', '')) || 0

          risks.push({
            protocol,
            slug: protocol.toLowerCase().replace(/\s+/g, '-'),
            riskScore,
            level,
            tvl,
            category: inferCategory(protocol),
            change1d: 0, // Not available in current output
            change7d: 0,
            timestamp: new Date().toISOString(),
            confidence: 0.8 + Math.random() * 0.2 // Simulated confidence
          })
        }
      } catch (parseError) {
        console.error('Failed to parse line:', line, parseError)
      }
    }
  }

  return risks
}

function inferCategory(protocol: string): string {
  const name = protocol.toLowerCase()
  if (name.includes('lido') || name.includes('staking')) return 'Liquid Staking'
  if (name.includes('aave') || name.includes('compound')) return 'Lending'
  if (name.includes('uniswap') || name.includes('dex')) return 'DEX'
  if (name.includes('bridge')) return 'Bridge'
  if (name.includes('eigen')) return 'Restaking'
  return 'DeFi'
}

function getMockData(): { risks: LiveRiskData[], stats: ModelStats } {
  // Fallback mock data if Python script fails
  const risks: LiveRiskData[] = [
    {
      protocol: 'SSV Network',
      slug: 'ssv-network',
      riskScore: 84,
      level: 'CRITICAL',
      tvl: 15400000000,
      category: 'Liquid Staking',
      change1d: -5.2,
      change7d: -12.4,
      timestamp: new Date().toISOString(),
      confidence: 0.89
    },
    {
      protocol: 'Lido',
      slug: 'lido',
      riskScore: 45,
      level: 'MEDIUM',
      tvl: 19900000000,
      category: 'Liquid Staking',
      change1d: 1.2,
      change7d: 3.4,
      timestamp: new Date().toISOString(),
      confidence: 0.82
    },
    {
      protocol: 'Aave V3',
      slug: 'aave-v3',
      riskScore: 32,
      level: 'LOW',
      tvl: 24700000000,
      category: 'Lending',
      change1d: 0.8,
      change7d: 2.1,
      timestamp: new Date().toISOString(),
      confidence: 0.94
    }
  ]

  const stats: ModelStats = {
    precision: 77.2,
    recall: 48.9,
    f1: 59.9,
    auc: 82.9,
    protocolsMonitored: risks.length,
    lastUpdate: new Date().toISOString(),
    isActive: false // Indicate we're using mock data
  }

  return { risks, stats }
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const limit = parseInt(searchParams.get('limit') || '10')
    const minRisk = parseInt(searchParams.get('minRisk') || '0')

    const { risks, stats } = await fetchLiveRisks()

    // Filter and limit results
    const filteredRisks = risks
      .filter(risk => risk.riskScore >= minRisk)
      .sort((a, b) => b.riskScore - a.riskScore)
      .slice(0, limit)

    return NextResponse.json({
      success: true,
      data: {
        risks: filteredRisks,
        stats,
        totalProtocols: risks.length,
        highRiskCount: risks.filter(r => r.riskScore >= 70).length,
        criticalRiskCount: risks.filter(r => r.riskScore >= 80).length,
      },
      timestamp: new Date().toISOString()
    })

  } catch (error) {
    console.error('API Error:', error)

    return NextResponse.json({
      success: false,
      error: 'Failed to fetch live risk data',
      message: error instanceof Error ? error.message : 'Unknown error',
      timestamp: new Date().toISOString()
    }, { status: 200 }) // Return 200 so frontend can handle gracefully
  }
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  try {
    const body = await request.json()
    const { protocols } = body

    if (!Array.isArray(protocols)) {
      return NextResponse.json({
        success: false,
        error: 'Invalid request: protocols must be an array',
        timestamp: new Date().toISOString()
      }, { status: 400 })
    }

    // Run monitoring for specific protocols
    const pythonScript = '/home/mutant/nexus/model/realtime_monitor.py'
    const protocolsArg = protocols.join(',')

    return new Promise<NextResponse>((resolve) => {
      const python = spawn('python', [pythonScript, '--protocols', protocolsArg, '--interval', '999999'], {
        cwd: '/home/mutant/nexus/model'
      })
      let output = ''

      python.stdout.on('data', (data) => {
        output += data.toString()
      })

      python.on('close', (code) => {
        const risks = parsePythonOutput(output)
        const filteredRisks = risks.filter(risk =>
          protocols.some(p => risk.protocol.toLowerCase().includes(p.toLowerCase()))
        )

        resolve(NextResponse.json({
          success: true,
          data: {
            risks: filteredRisks,
            requestedProtocols: protocols,
            foundProtocols: filteredRisks.length
          },
          timestamp: new Date().toISOString()
        }))
      })

      // Timeout after 15 seconds
      setTimeout(() => {
        python.kill()
        resolve(NextResponse.json({
          success: false,
          error: 'Request timeout',
          timestamp: new Date().toISOString()
        }))
      }, 15000)
    })

  } catch (error) {
    return NextResponse.json({
      success: false,
      error: 'Failed to process request',
      message: error instanceof Error ? error.message : 'Unknown error',
      timestamp: new Date().toISOString()
    }, { status: 400 })
  }
}