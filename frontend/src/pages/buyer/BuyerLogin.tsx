import { LoginForm } from '../../components/LoginForm'
import { buyerLogin } from '../../services/api'

export default function BuyerLogin() {
  return (
    <LoginForm
      title="Buyer Sign In"
      role="buyer"
      loginFn={buyerLogin}
      afterLoginPath="/buyer/marketplace"
      backPath="/"
      demoEmail="procurement@freshmart.com"
    />
  )
}
