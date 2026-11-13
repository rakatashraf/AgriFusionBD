import { defineConfig } from '@hey-api/openapi-ts'

export default defineConfig({
  input: 'https://fieldshift.zws.bd/api/schema/',
  output: {
    path: 'src/generated/api',
  },
  plugins: ['@hey-api/typescript'],
})
