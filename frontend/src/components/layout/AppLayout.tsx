import { useState } from "react"
import { Outlet } from "react-router-dom"
import { Menu } from "lucide-react"
import { Sidebar } from "./Sidebar"
import { SchedulerBar } from "./SchedulerBar"

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-14 items-center gap-4 border-b border-border/60 bg-card/50 px-4 lg:px-6 backdrop-blur-sm">
          <button
            onClick={() => setSidebarOpen(true)}
            className="lg:hidden text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
          >
            <Menu className="h-5 w-5" />
          </button>
          <SchedulerBar />
        </header>

        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          <div className="animate-fade-in">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
