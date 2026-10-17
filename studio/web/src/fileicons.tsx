import { Braces, Database, File, FileCode2, FileText, FolderClosed, FolderOpen, Settings2, Table2, Terminal } from 'lucide-react'

const BY_EXT: Record<string, { icon: typeof File; color: string }> = {
  py: { icon: FileCode2, color: '#6fa8e6' },
  pyi: { icon: FileCode2, color: '#6fa8e6' },
  cpp: { icon: FileCode2, color: '#b59cf5' },
  hpp: { icon: FileCode2, color: '#b59cf5' },
  c: { icon: FileCode2, color: '#b59cf5' },
  h: { icon: FileCode2, color: '#b59cf5' },
  json: { icon: Braces, color: '#f0c36a' },
  md: { icon: FileText, color: '#9aa3b5' },
  txt: { icon: FileText, color: '#7f8798' },
  sh: { icon: Terminal, color: '#6fd3a2' },
  toml: { icon: Settings2, color: '#e59b6a' },
  yaml: { icon: Settings2, color: '#e59b6a' },
  yml: { icon: Settings2, color: '#e59b6a' },
  cfg: { icon: Settings2, color: '#e59b6a' },
  csv: { icon: Table2, color: '#6fd3a2' },
  npy: { icon: Database, color: '#e58aa8' },
  bin: { icon: Database, color: '#7f8798' },
}

export function FileIcon({ name, size = 14, className }: { name: string; size?: number; className?: string }) {
  const ext = name.includes('.') ? name.split('.').pop()!.toLowerCase() : ''
  const m = BY_EXT[ext] ?? { icon: File, color: '#7f8798' }
  const I = m.icon
  return <I size={size} className={className ?? 'flex-none'} style={{ color: m.color }} strokeWidth={1.8} />
}

export function FolderIcon({ open, size = 14 }: { open?: boolean; size?: number }) {
  const I = open ? FolderOpen : FolderClosed
  return <I size={size} className="flex-none text-accent/70" strokeWidth={1.8} />
}
