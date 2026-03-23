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
  Rocket,
  Zap,
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
  { to: "/auto-launcher", icon: Rocket, label: "Auto-Launcher" },
  { to: "/settings", icon: Settings, label: "Settings" },
]

interface Props {
  open: boolean
  onClose: () => void
}

export function Sidebar({ open, onClose }: Props) {
  const { user, signOut } = useAuth()

  return (
    <>
      {open && (
        <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden" onClick={onClose} />
      )}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-sidebar-border bg-sidebar transition-transform duration-300 ease-out lg:static lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        {/* Logo */}
        <div className="flex h-14 items-center gap-2.5 border-b border-sidebar-border px-5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/15">
            <Zap className="h-4 w-4 text-primary" />
          </div>
          <span className="text-base font-bold tracking-tight">FB Budget</span>
          <button onClick={onClose} className="ml-auto lg:hidden text-muted-foreground hover:text-foreground cursor-pointer">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-0.5 px-3 py-4">
          {links.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              onClick={onClose}
              className={({ isActive }) =>
                cn(
                  "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200",
                  isActive
                    ? "bg-primary/10 text-primary shadow-sm"
                    : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
                )
              }
              end={to === "/"}
            >
              {({ isActive }) => (
                <>
                  <div
                    className={cn(
                      "flex h-7 w-7 items-center justify-center rounded-md transition-colors duration-200",
                      isActive
                        ? "bg-primary/15 text-primary"
                        : "text-muted-foreground group-hover:text-foreground",
                    )}
                  >
                    <Icon className="h-4 w-4" />
                  </div>
                  {label}
                  {isActive && (
                    <div className="ml-auto h-1.5 w-1.5 rounded-full bg-primary" />
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* User section */}
        <div className="border-t border-sidebar-border p-3 space-y-1">
          {user?.email && (
            <div className="px-3 py-1.5 text-xs text-muted-foreground truncate">
              {user.email}
            </div>
          )}
          <button
            onClick={() => signOut()}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent/60 hover:text-foreground cursor-pointer"
          >
            <div className="flex h-7 w-7 items-center justify-center rounded-md">
              <LogOut className="h-4 w-4" />
            </div>
            Logout
          </button>
        </div>
      </aside>
    </>
  )
}
