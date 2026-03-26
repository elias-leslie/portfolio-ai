'use client'

import { NotesProvider, NotesPanel } from '@summitflow/notes-ui'

export default function NotesPopoutPage() {
  return (
    <NotesProvider apiPrefix="/api" projectScope="portfolio-ai">
      <div className="flex h-screen flex-col bg-slate-950">
        <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800">
          <span className="text-xs font-medium text-slate-400 tracking-wide">Notes</span>
          <span className="text-[10px] text-slate-500">project: portfolio-ai</span>
        </div>
        <div className="flex flex-col flex-1 min-h-0">
          <NotesPanel />
        </div>
      </div>
    </NotesProvider>
  )
}
