// 안드로이드에서 FastAPI 로컬 서버에 접속하는 URL 예시

// 예를 들어 PC의 IP가 192.168.0.12이고 FastAPI가 8000 포트에서 실행 중이라면:
val serverUrl = "http://192.168.0.12:8000/your_endpoint"

// OkHttp 또는 Retrofit 등에서 이 URL을 기반으로 서버 요청을 보낼 수 있음

// 예시 (OkHttp)
val client = OkHttpClient()
val request = Request.Builder()
    .url(serverUrl)
    .build()

client.newCall(request).enqueue(object : Callback {
    override fun onFailure(call: Call, e: IOException) {
        // 실패 처리
    }

    override fun onResponse(call: Call, response: Response) {
        // 응답 처리
    }
})

### 주의사항:
// - PC 방화벽에서 8000 포트를 열어야 함
// - 안드로이드 기기와 PC는 같은 Wi-Fi에 있어야 함
// - localhost 또는 127.0.0.1을 사용하면 안드로이드 기기 자신의 루프백 주소를 의미하므로 접속 불가