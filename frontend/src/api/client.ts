import axios from 'axios'
import { ElMessage } from 'element-plus'

const client = axios.create({ baseURL: '/api/v1', timeout: 15_000 })
client.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    const message = axios.isAxiosError(error) ? String(error.response?.data?.detail ?? error.message) : 'Unexpected request error'
    ElMessage.error(message)
    return Promise.reject(error)
  }
)
export default client
