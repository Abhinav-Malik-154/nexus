import { NextRequest, NextResponse } from 'next/server'
import { exec } from 'child_process'
import { promisify } from 'util'

const execAsync = promisify(exec)

export async function GET() {
  try {
    // Execute live security feed Python script with absolute path
    const { stdout, stderr } = await execAsync(
      'cd /home/mutant/nexus/model && /usr/bin/python3 live_security_feed.py',
      { timeout: 15000 } // Reduced timeout for faster response
    )

    if (stderr && stderr.trim()) {
      console.error('Live security feed stderr:', stderr)
      // Still try to parse stdout in case script worked despite warnings
    }

    if (!stdout || stdout.trim() === '') {
      throw new Error('No output from security feed script')
    }

    const securityData = JSON.parse(stdout)

    // Validate the response structure
    if (!securityData || typeof securityData !== 'object') {
      throw new Error('Invalid response format from security feed')
    }

    return NextResponse.json({
      success: true,
      data: securityData,
      timestamp: new Date().toISOString()
    })

  } catch (error) {
    console.error('Security feed API error:', error)
    return NextResponse.json({
      success: false,
      error: error instanceof Error ? error.message : 'Security intelligence service unavailable',
      fallback: generateFallbackData()
    }, { status: 200 }) // Return 200 with fallback data for better UX
  }
}

function generateFallbackData() {
  return {
    threats: [
      {
        id: 'emergency',
        title: 'Live Security Feed Temporarily Unavailable',
        severity: 'HIGH',
        date: new Date().toISOString(),
        timeAgo: 'Now',
        type: 'System Alert',
        source: 'nexus.system'
      }
    ],
    summary: {
      total: 1,
      critical: 0,
      high: 1,
      last_updated: new Date().toISOString()
    }
  }
}

export async function POST() {
  return NextResponse.json({ error: 'Method not allowed' }, { status: 405 })
}