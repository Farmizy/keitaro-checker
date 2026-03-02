import { NavLink } from "react-router-dom"
import {
  LayoutDashboard,
  Users,
  Megaphone,
  Scale,
  ScrollText,
  Settings,
  LogOut,
  X,
  PlusCircle,
} from "lucide-react"
import { useAuth } from "@/hooks/useAuth"
import { cn } from "@/lib/utils"

const links = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/accounts", icon: Users, label: "Accounts" },
  { to: "/campaigns", icon: Megaphone, label: "Campaigns" },
  { to: "/rules", icon: Scale, label: "Rules" },
  { to: "/logs", icon: ScrollText, label: "Logs" },
  { to: "/generator", icon: PlusCircle, label: "Generator" },
  { to: "/settings", icon: Settings, label: "Settings" },
]

interface Props {
  open: boolean
  onClose: () => void
}

export function Sidebar({ open, onClose }: Props) {
  const { signOut } = useAuth()

  return (
    <>
      {open && (
        <div className="fixed inset-0 z-40 bg-black/50 lg:hidden" onClick={onClose} />
      )}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-transform lg:static lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-14 items-center justify-between border-b border-sidebar-border px-4">
          <span className="text-lg font-bold tracking-tight">FB Budget</span>
          <button onClick={onClose} className="lg:hidden text-muted-foreground hover:text-foreground cursor-pointer">
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {links.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              onClick={onClose}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                )
              }
              end={to === "/"}
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-sidebar-border p-3">
          <button
            onClick={() => signOut()}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent/50 hover:text-foreground cursor-pointer"
          >
            <LogOut className="h-4 w-4" />
            Logout
          </button>
        </div>
      </aside>
    </>
  )
}
