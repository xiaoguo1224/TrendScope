import axios from 'axios'
import { ElMessage } from 'element-plus'

// Ordinary API reads remain bounded; long-running collection and explicit
// model-generation requests override this with their own user-visible budget.
const client = axios.create({ baseURL: '/api/v1', timeout: 60_000 })
client.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    const message = axios.isAxiosError(error) ? String(error.response?.data?.detail ?? error.message) : 'Unexpected request error'
    ElMessage.error(message)
    return Promise.reject(error)
  }
)
export default client
