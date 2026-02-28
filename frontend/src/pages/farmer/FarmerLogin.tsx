import { LoginForm } from '../../components/LoginForm'
import { farmerLogin } from '../../services/api'

export default function FarmerLogin() {
  return (
    <LoginForm
      title="Farmer Sign In"
      role="farmer"
      loginFn={farmerLogin}
      afterLoginPath="/farmer/dashboard"
      backPath="/"
      demoEmail="ravi@demofarm.com"
    />
  )
}
