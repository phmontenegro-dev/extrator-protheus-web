import { useNavigate } from 'react-router-dom'
import { Compass, Home } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Logo } from '@/components/Logo'

export default function NotFound() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-background">
      <div className="w-full max-w-md text-center">
        <div className="flex justify-center mb-8">
          <Logo className="scale-125" />
        </div>

        <div className="flex justify-center mb-4">
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-accent text-accent-foreground">
            <Compass className="h-10 w-10" />
          </div>
        </div>

        <h1 className="text-6xl font-bold text-primary tracking-tight mb-2">404</h1>
        <h2 className="text-xl font-semibold mb-2">Página não encontrada</h2>
        <p className="text-sm text-muted-foreground mb-8">
          O endereço que você acessou não existe ou foi movido.
        </p>

        <div className="flex items-center justify-center gap-2">
          <Button onClick={() => navigate(-1)} variant="outline">
            Voltar
          </Button>
          <Button onClick={() => navigate('/menu')}>
            <Home className="h-4 w-4" />
            Ir ao menu
          </Button>
        </div>
      </div>
    </div>
  )
}
