'use client'

import { getServerUrl, getWsUrl } from '@/lib/server-url'
import type { Dispatch, SetStateAction } from 'react'
import { useRef, useState } from 'react'
import type { AgentProvider, RoundtableOrder } from '../AgentSelector'
import type { AgentMode } from '../ModeSelector'
import type { ContentBlock, PermissionRequest } from '../wsHandlers'
import type { ChatMessage } from '../wsHandlers'

export interface UseAgentPanelStateReturn {
  // Server/connection state
  serverUrl: string | null
  wsUrl: string | null
  isConnected: boolean
  connectionError: string | null
  setIsConnected: Dispatch<SetStateAction<boolean>>
  setConnectionError: Dispatch<SetStateAction<string | null>>

  // Chat state
  messages: ChatMessage[]
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>
  input: string
  setInput: (v: string) => void
  isLoading: boolean
  setIsLoading: React.Dispatch<React.SetStateAction<boolean>>
  currentResponse: ContentBlock[]
  setCurrentResponse: React.Dispatch<React.SetStateAction<ContentBlock[]>>
  pendingPermission: PermissionRequest | null
  setPendingPermission: React.Dispatch<
    React.SetStateAction<PermissionRequest | null>
  >

  // Agent/mode state
  agentProvider: AgentProvider
  setAgentProvider: (v: AgentProvider) => void
  agentMode: AgentMode
  setAgentMode: (v: AgentMode) => void
  roundtableOrder: RoundtableOrder
  setRoundtableOrder: (v: RoundtableOrder) => void
  maxTurns: number
  setMaxTurns: (v: number) => void
  currentRespondingAgent: 'claude' | 'gemini' | null
  setCurrentRespondingAgent: React.Dispatch<
    React.SetStateAction<'claude' | 'gemini' | null>
  >

  // Refs
  messagesEndRef: React.RefObject<HTMLDivElement | null>
  currentResponseRef: React.MutableRefObject<ContentBlock[]>
}

export function useAgentPanelState(): UseAgentPanelStateReturn {
  const [serverUrl] = useState<string | null>(() => getServerUrl())
  const [wsUrl] = useState<string | null>(() => {
    const url = getServerUrl()
    return url ? getWsUrl(url) : null
  })
  const [isConnected, setIsConnected] = useState(false)
  const [connectionError, setConnectionError] = useState<string | null>(null)

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [currentResponse, setCurrentResponse] = useState<ContentBlock[]>([])
  const [pendingPermission, setPendingPermission] =
    useState<PermissionRequest | null>(null)

  const [agentProvider, setAgentProvider] = useState<AgentProvider>('claude')
  const [agentMode, setAgentMode] = useState<AgentMode>('dev')
  const [roundtableOrder, setRoundtableOrder] =
    useState<RoundtableOrder>('claude-first')
  const [maxTurns, setMaxTurns] = useState<number>(10)
  const [currentRespondingAgent, setCurrentRespondingAgent] = useState<
    'claude' | 'gemini' | null
  >(null)

  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const currentResponseRef = useRef<ContentBlock[]>([])

  return {
    serverUrl,
    wsUrl,
    isConnected,
    connectionError,
    setIsConnected,
    setConnectionError,
    messages,
    setMessages,
    input,
    setInput,
    isLoading,
    setIsLoading,
    currentResponse,
    setCurrentResponse,
    pendingPermission,
    setPendingPermission,
    agentProvider,
    setAgentProvider,
    agentMode,
    setAgentMode,
    roundtableOrder,
    setRoundtableOrder,
    maxTurns,
    setMaxTurns,
    currentRespondingAgent,
    setCurrentRespondingAgent,
    messagesEndRef,
    currentResponseRef,
  }
}
