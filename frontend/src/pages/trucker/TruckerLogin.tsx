import { LoginForm } from '../../components/LoginForm'
import { truckerLogin } from '../../services/api'

export default function TruckerLogin() {
  return (
    <LoginForm
      title="Trucker Sign In"
      role="trucker"
      loginFn={truckerLogin}
      afterLoginPath="/trucker/routes"
      backPath="/"
      demoEmail="mohammed.faiz@demo.com"
    />
  )
}
