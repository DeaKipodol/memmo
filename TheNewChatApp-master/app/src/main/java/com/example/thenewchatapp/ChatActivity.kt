package com.example.thenewchatapp

import android.animation.ValueAnimator
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.EditText
import android.widget.ImageButton
import android.widget.PopupMenu
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.graphics.ColorUtils
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import kotlinx.coroutines.*
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import androidx.activity.viewModels
import android.widget.RelativeLayout
import android.widget.FrameLayout
import androidx.appcompat.app.AppCompatDelegate
import com.example.thenewchatapp.MainActivity.Companion.prefs
import android.graphics.Rect
import android.graphics.drawable.GradientDrawable
import android.text.Editable
import android.text.TextWatcher
import android.util.Log
import android.view.ViewTreeObserver
import android.widget.Toast
import androidx.core.content.ContextCompat
import java.util.concurrent.TimeUnit
import java.io.IOException
class ChatActivity : AppCompatActivity() {

    private lateinit var chatRecyclerView: RecyclerView
    private lateinit var messageEditText: EditText
    private lateinit var sendButton: ImageButton
    private lateinit var goToEditButton: ImageButton
    private lateinit var createResultButton: ImageButton
    private lateinit var btnPlus: ImageButton
    private lateinit var btnVoice: ImageButton
    private lateinit var recyclerCategory: RecyclerView
    private lateinit var recyclerEntry: RecyclerView
    private val viewModel: FieldViewModel by viewModels()
    private lateinit var chatContainer: RelativeLayout
    private lateinit var fragmentContainer: FrameLayout

    private val chatMessages = mutableListOf<ChatMessage>()
    private lateinit var chatAdapter: ChatAdapter

    private lateinit var categoryAdapter: EasyCommandCategoryAdapter
    private lateinit var entryAdapter: EasyCommandEntryAdapter

    private lateinit var inputArea: FrameLayout
    private var isEasyCommandVisible = false
    private lateinit var recyclerEasyCommand: RecyclerView
    private lateinit var recyclerCommandEntry: RecyclerView



    private val easyCommandMap = mutableMapOf(
        "요약" to mutableListOf("간단 요약: 이 내용을 간단하게 요약해줘"),
        "다듬기" to mutableListOf("문장 정리: 더 자연스럽게 바꿔줘"),
        "늘리기" to mutableListOf("내용 확장: 더 길게 써줘")
    )

    private var currentCategory: String = easyCommandMap.keys.first()

    private val fields = listOf(
        Field("목적", ""), Field("주제", ""), Field("독자", ""), Field("형식 혹은 구조", ""),
        Field("근거자료", ""), Field("어조", ""), Field("분량, 문체, 금지어 등", ""), Field("추가사항", "")
    )

    private val fieldKeys = listOf(
        "목적","주제","독자","형식 혹은 구조",
        "근거자료","어조","분량, 문체, 금지어 등","추가사항"
    )

    private val editMessageLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            val editedText = result.data?.getStringExtra("editedText")
            val position = result.data?.getIntExtra("messagePosition", -1) ?: -1
            if (position in chatMessages.indices && editedText != null) {
                chatMessages[position] = chatMessages[position].copy(message = editedText)
                chatAdapter.notifyItemChanged(position)
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        prefs = getSharedPreferences("settings", MODE_PRIVATE)
        AppCompatDelegate.setDefaultNightMode(
            prefs.getInt("theme_mode", AppCompatDelegate.MODE_NIGHT_FOLLOW_SYSTEM)
        )

        super.onCreate(savedInstanceState)
        window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE)
        setContentView(R.layout.activity_chat)

        // 시스템 바/IME 패딩 처리
        val mainView = findViewById<View>(R.id.mainLayout)
        ViewCompat.setOnApplyWindowInsetsListener(mainView) { v, insets ->
            val sys = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            val ime = insets.getInsets(WindowInsetsCompat.Type.ime())
            v.setPadding(sys.left, sys.top, sys.right, sys.bottom + ime.bottom)
            insets
        }

        // 뷰 바인딩
        chatRecyclerView = findViewById(R.id.chat_recyclerView)
        messageEditText = findViewById(R.id.editTextInput)
        sendButton = findViewById(R.id.btnSend)
        goToEditButton = findViewById(R.id.goToEditButton)
        createResultButton = findViewById(R.id.CreateResultButton)
        btnPlus         = findViewById(R.id.btnPlus)
        recyclerCategory= findViewById(R.id.recyclerEasyCommand)
        recyclerEntry   = findViewById(R.id.recyclerCommandEntry)
        btnVoice = findViewById(R.id.btnVoice)
        chatContainer     = findViewById(R.id.chatContainer)
        fragmentContainer = findViewById(R.id.fragmentContainer)

        inputArea = findViewById(R.id.inputArea)
        recyclerEasyCommand = findViewById(R.id.recyclerEasyCommand)
        recyclerCommandEntry = findViewById(R.id.recyclerCommandEntry)


        // ViewModel 기본 제목 초기화 (한 번만)
        viewModel.initTitles(fieldKeys)

        // **1) ViewModel에 기본 필드명 채우기**
        val fieldKeys = fields.map { it.title }
        viewModel.initTitles(fieldKeys)

        // EasyCommand 리스트 기본 숨김
        recyclerCategory.visibility = View.GONE
        recyclerEntry.visibility   = View.GONE

        // 상단 EasyCommand 카테고리
        recyclerCategory.layoutManager =
            LinearLayoutManager(this, LinearLayoutManager.HORIZONTAL, false)
        categoryAdapter = EasyCommandCategoryAdapter(
            easyCommandMap.keys.toList(),
            onCategoryClick = { selected ->
                currentCategory = selected
                updateEntryList()
            },
            onDeleteConfirmed = { category ->
                easyCommandMap.remove(category)
                refreshCategoryAdapter()
            }
        ).apply {
            setOnAddCategoryClickListener { showAddCategoryDialog() }
        }
        recyclerCategory.adapter = categoryAdapter

        // 하단 EasyCommand 엔트리
        recyclerEntry.layoutManager = LinearLayoutManager(this)
        entryAdapter = EasyCommandEntryAdapter(
            entries = emptyList(),
            onEditClick = { title, prompt -> openDetail(title, prompt) },
            onDeleteClick = { title ->
                easyCommandMap[currentCategory]?.removeIf { it.startsWith(title) }
                updateEntryList()
            },
            onPromptClick = { prompt -> messageEditText.setText(prompt) },
            onAddClick = { openDetail(null, null) }
        )
        recyclerEntry.adapter = entryAdapter

        // ➕ 버튼 팝업 메뉴
        btnPlus.setOnClickListener { anchorView ->
            PopupMenu(this, anchorView).apply {
                menu.add("일반 글 화면").setOnMenuItemClickListener {
                    startActivity(Intent(this@ChatActivity, MainActivity::class.java))
                    true
                }
                menu.add("필드 화면").setOnMenuItemClickListener {
                    startActivity(Intent(this@ChatActivity, FieldActivity::class.java))
                    true
                }
                menu.add("이지커맨드").setOnMenuItemClickListener {
                    dismiss()
                    recyclerEasyCommand.post {
                        showEasyCommandLists()
                    }
                    true
                }
                setOnDismissListener {
                    // 팝업 닫힐 때 별도 처리 필요없으면 비워둬도 됨
                }
                show()
            }
        }



        // 초기 엔트리 리스트 세팅
        updateEntryList()

        // **5+7. CommandDetailFragment에서 온 저장 결과 받기**
        supportFragmentManager.setFragmentResultListener(
            "easy_command_save", this
        ) { key, bundle ->
            val original = bundle.getString("original") ?: ""
            val title = bundle.getString("title") ?: return@setFragmentResultListener
            val prompt = bundle.getString("prompt") ?: return@setFragmentResultListener
            easyCommandMap[currentCategory]?.let { commands ->       // 바깥 it → commands 로 변경
                if (original.isNotBlank()) {
                    commands.removeIf { entry ->                      // 중첩 람다의 it → entry 로 변경
                        entry.startsWith("$original:")                // 문자열 템플릿 사용
                    }
                }
                // 새로 추가
                commands.add("$title:$prompt")
            }

            updateEntryList()
        }

        //   **1. 포커스 해제 시 숨김 (이미 구현)**
//        messageEditText.setOnFocusChangeListener { _, hasFocus ->
//            if (hasFocus) {
//                recyclerCategory.visibility = View.VISIBLE
//                recyclerEntry.visibility = View.VISIBLE
//            } else {
//                recyclerCategory.visibility = View.GONE
//                recyclerEntry.visibility = View.GONE
//            }
//        }

        // 이지커맨드가 열려있을 때 입력필드 포커스 생기면 이지커맨드 닫기
        messageEditText.setOnFocusChangeListener { _, hasFocus ->
            if (hasFocus) {
                if (isEasyCommandVisible) {
                    hideEasyCommandLists()
                }
            }
        }




        // 결과 생성 버튼 클릭
        createResultButton.setOnClickListener {
            // 1) 결과 전용 로딩 메시지 추가
            val loading = ChatMessage("결과 생성 중 입니다...", MessageType.LOADING_RESULT)
            chatMessages.add(loading)
            chatAdapter.notifyItemInserted(chatMessages.lastIndex)
            chatRecyclerView.smoothScrollToPosition(chatMessages.lastIndex)

            // 2) 실제 API 호출
            CoroutineScope(Dispatchers.IO).launch {
                val client = OkHttpClient.Builder()
                    .connectTimeout(0, TimeUnit.SECONDS)  // 0은 무한대기. 일반적으로 권장되지 않음. 적절한 값으로 설정 필요 (예: 30)
                    .readTimeout(0, TimeUnit.SECONDS)    // 0은 무한대기. 장시간 작업 시 사용 가능하나, UX 고려 필요.
                    .writeTimeout(0, TimeUnit.SECONDS)   // 0은 무한대기. 일반적으로 권장되지 않음. 적절한 값으로 설정 필요 (예: 30)
                    .build()
                val serverUrl = "http://54.252.159.52:5000/generate-document"

                val requestBody: RequestBody = "".toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

                // Request 객체 생성 추가
                val request = Request.Builder()
                    .url(serverUrl)       // serverUrl 사용
                    .post(requestBody)    // requestBody 사용
                    .build()

                var resultText: String? = null
                var requestSuccessful = false
                var errorMessageText: String? = null
                try {
                    // client.newCall에 request 변수 전달
                    val response = client.newCall(request).execute()

                    if (response.isSuccessful) {
                        val responseBodyString = response.body?.string()
                        if (responseBodyString != null) {
                            try {
                                val jsonResponse = JSONObject(responseBodyString)
                                requestSuccessful = jsonResponse.optBoolean("success", false)

                                if (requestSuccessful) {
                                    resultText = jsonResponse.optString(
                                        "final_text",
                                        "서버로부터 결과 텍스트를 받지 못했습니다."
                                    )
                                } else {
                                    errorMessageText =
                                        jsonResponse.optString("detail", "서버에서 요청 처리에 실패했습니다.")
                                    if (errorMessageText.isNullOrEmpty()) {
                                        errorMessageText = jsonResponse.optString(
                                            "final_text",
                                            "서버에서 요청 처리에 실패했으며, 상세 오류 메시지가 없습니다."
                                        )
                                    }
                                }
                            } catch (e: org.json.JSONException) {
                                requestSuccessful = false
                                errorMessageText = "서버 응답을 처리하는 중 오류가 발생했습니다. (JSON 파싱 오류)"
                                e.printStackTrace()
                            }
                        } else {
                            requestSuccessful = false
                            errorMessageText = "서버로부터 비어있는 응답을 받았습니다."
                        }
                    } else {
                        requestSuccessful = false
                        val errorBodyString = response.body?.string()
                        var detailMessage = response.message

                        if (!errorBodyString.isNullOrEmpty()) {
                            try {
                                val errorJson = JSONObject(errorBodyString)
                                detailMessage = errorJson.optString("detail", detailMessage)
                            } catch (e: org.json.JSONException) {
                                e.printStackTrace()
                            }
                        }
                        errorMessageText =
                            "결과 생성에 실패했습니다. (서버 오류: ${response.code} ${detailMessage})"
                    }
                } catch (e: IOException) {
                    requestSuccessful = false
                    errorMessageText = "네트워크 연결 중 오류가 발생했습니다: ${e.localizedMessage}"
                    e.printStackTrace()
                }

                withContext(Dispatchers.Main) {
                    val loadingIdx = chatMessages.indexOf(loading)
                    if (loadingIdx >= 0) {
                        chatMessages.removeAt(loadingIdx)
                        chatAdapter.notifyItemRemoved(loadingIdx)
                    }

                    val messageToShow: ChatMessage
                    if (requestSuccessful && resultText != null) {
                        messageToShow = ChatMessage(resultText, MessageType.RECEIVED, isResult = true)
                    } else {
                        val finalErrorMessage = errorMessageText ?: "알 수 없는 오류로 인해 결과를 생성할 수 없습니다."
                        messageToShow = ChatMessage(finalErrorMessage, MessageType.RECEIVED, isResult = true)
                    }
                    chatMessages.add(messageToShow)
                    chatAdapter.notifyItemInserted(chatMessages.lastIndex)
                    chatRecyclerView.smoothScrollToPosition(chatMessages.lastIndex)
                }
            }
        }

        // MainActivity로 편집 이동
        goToEditButton.setOnClickListener {
            val intent = Intent(this, MainActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            }
            startActivity(intent)
        }

        // RecyclerView 설정
        chatRecyclerView.layoutManager = LinearLayoutManager(this).apply { stackFromEnd = false }
        chatAdapter = ChatAdapter(chatMessages) { pos, text ->
            val intent = Intent(this, MainActivity::class.java).apply {
                putExtra("originalText", text)
                putExtra("messagePosition", pos)
            }
            editMessageLauncher.launch(intent)
        }
        chatRecyclerView.adapter = chatAdapter

        // 초기 대화 처리
        intent.getStringExtra("conversation")?.takeIf { it.isNotEmpty() }?.let {
            chatMessages += ChatMessage(it, MessageType.SENT)
            chatAdapter.notifyItemInserted(chatMessages.lastIndex)
            chatRecyclerView.smoothScrollToPosition(chatMessages.lastIndex)
            val reply = externalReply(it)
            chatMessages += ChatMessage(reply, MessageType.RECEIVED)
            chatAdapter.notifyItemInserted(chatMessages.lastIndex)
            chatRecyclerView.smoothScrollToPosition(chatMessages.lastIndex)
        }

        // 전송 버튼 클릭
        sendButton.setOnClickListener {
            val text = messageEditText.text.toString().trim()
            if (text.isNotEmpty()) {
                // 사용자 메시지 추가
                chatMessages += ChatMessage(text, MessageType.SENT)
                chatAdapter.notifyItemInserted(chatMessages.lastIndex)
                chatRecyclerView.smoothScrollToPosition(chatMessages.lastIndex)
                messageEditText.text.clear()

                // 일반 로딩 메시지 추가
                val loading = ChatMessage("답변 생성 중 입니다...", MessageType.LOADING)
                chatMessages += loading
                chatAdapter.notifyItemInserted(chatMessages.lastIndex)
                chatRecyclerView.smoothScrollToPosition(chatMessages.lastIndex)

                // AI 응답 스트리밍
                CoroutineScope(Dispatchers.Main).launch {
                    val response = ChatMessage("", MessageType.RECEIVED)
                    chatAdapter.sendChatRequest(text) { chunk ->
                        if (loading in chatMessages) {
                            val idx = chatMessages.indexOf(loading)
                            chatMessages.removeAt(idx)
                            chatAdapter.notifyItemRemoved(idx)
                        }
                        if (response !in chatMessages) {
                            chatMessages += response
                            chatAdapter.notifyItemInserted(chatMessages.lastIndex)
                        }
                        response.message += chunk
                        chatAdapter.notifyItemChanged(chatMessages.indexOf(response))
                        chatRecyclerView.smoothScrollToPosition(chatMessages.lastIndex)
                    }
                }
            }
        }

        btnVoice.setOnClickListener {
            Toast.makeText(this, "음성 인식이 시작됩니다.", Toast.LENGTH_SHORT).show()
        }


        // 챗봇창 입력 필드 글자수에 따라서 radius 자동 변경되는 코드
        messageEditText.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) {
                // UI 업데이트를 보장하기 위해 post 사용
                messageEditText.post {
                    val lineCount = messageEditText.lineCount
                    val density = messageEditText.resources.displayMetrics.density

                    val maxRadius = 100f * density
                    val minRadius = 10f * density

                    val radius = (maxRadius - (lineCount - 1) * 50f * density).coerceAtLeast(minRadius)

                    val bgDrawable = GradientDrawable().apply {
                        setColor(ContextCompat.getColor(messageEditText.context, R.color.grey2))
                        cornerRadius = radius
                    }

                    messageEditText.background = bgDrawable
                }
            }

            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
        })


        setupKeyboardListener()


    }

    private fun externalReply(sentMsg: String): String = "Reply to: $sentMsg"

    class ChatAdapter(
        private val messages: List<ChatMessage>,
        private val onReceivedClick: (Int, String) -> Unit
    ) : RecyclerView.Adapter<RecyclerView.ViewHolder>() {

        companion object {
            private const val VIEW_TYPE_SENT = 1
            private const val VIEW_TYPE_RECEIVED = 2
            private const val VIEW_TYPE_RESULT = 3
            private const val VIEW_TYPE_LOADING = 4
            private const val VIEW_TYPE_LOADING_RESULT = 5
        }

        override fun getItemViewType(position: Int): Int = with(messages[position]) {
            when {
                type == MessageType.SENT               -> VIEW_TYPE_SENT
                type == MessageType.LOADING_RESULT     -> VIEW_TYPE_LOADING_RESULT
                type == MessageType.LOADING            -> VIEW_TYPE_LOADING
                type == MessageType.RECEIVED && isResult -> VIEW_TYPE_RESULT
                else                                   -> VIEW_TYPE_RECEIVED
            }
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): RecyclerView.ViewHolder =
            LayoutInflater.from(parent.context).run {
                when (viewType) {
                    VIEW_TYPE_SENT           -> SentViewHolder(inflate(R.layout.sent_message_bubble, parent, false))
                    VIEW_TYPE_LOADING_RESULT -> ResultLoadingViewHolder(inflate(R.layout.result_loading_message_bubble, parent, false))
                    VIEW_TYPE_LOADING        -> LoadingViewHolder(inflate(R.layout.loading_message_bubble, parent, false))
                    VIEW_TYPE_RESULT         -> ResultViewHolder(inflate(R.layout.result_received_message_bubble, parent, false))
                    else                     -> ReceivedViewHolder(inflate(R.layout.received_message_bubble, parent, false))
                }
            }

        override fun getItemCount(): Int = messages.size

        override fun onBindViewHolder(holder: RecyclerView.ViewHolder, position: Int) {
            val msg = messages[position]
            when (holder) {
                is SentViewHolder           -> holder.bind(msg)
                is ReceivedViewHolder       -> holder.bind(msg)
                is ResultViewHolder         -> holder.bind(msg, onReceivedClick)
                is LoadingViewHolder        -> holder.bind()
                is ResultLoadingViewHolder  -> holder.bind()
            }
        }

        class SentViewHolder(view: View) : RecyclerView.ViewHolder(view) {
            private val tv: TextView = view.findViewById(R.id.sent_message_bubble)
            fun bind(msg: ChatMessage) { tv.text = msg.message }
        }

        class ReceivedViewHolder(view: View) : RecyclerView.ViewHolder(view) {
            private val tv: TextView = view.findViewById(R.id.receive_message_bubble)
            fun bind(msg: ChatMessage) { tv.apply { text = msg.message; setOnClickListener(null) } }
        }

        class ResultViewHolder(view: View) : RecyclerView.ViewHolder(view) {
            private val tv: TextView = view.findViewById(R.id.result_receive_message_bubble)
            fun bind(msg: ChatMessage, click: (Int, String) -> Unit) {
                tv.text = msg.message
                tv.setOnClickListener { click(adapterPosition, msg.message) }
            }
        }

        class LoadingViewHolder(view: View) : RecyclerView.ViewHolder(view) {
            private val tv: TextView = view.findViewById(R.id.loading_text)
            private var animator: ValueAnimator? = null
            fun bind() {
                val base = tv.currentTextColor
                animator?.cancel()
                animator = ValueAnimator.ofFloat(0.3f, 1f).apply {
                    duration = 1000
                    repeatMode = ValueAnimator.REVERSE
                    repeatCount = ValueAnimator.INFINITE
                    addUpdateListener {
                        val a = (it.animatedValue as Float * 255).toInt()
                        tv.setTextColor(ColorUtils.setAlphaComponent(base, a))
                    }
                    start()
                }
                tv.text = "답변 생성 중 입니다..."
            }
        }

        class ResultLoadingViewHolder(view: View) : RecyclerView.ViewHolder(view) {
            private val tv: TextView = view.findViewById(R.id.result_loading_text)
            private var animator: ValueAnimator? = null
            fun bind() {
                val base = tv.currentTextColor
                animator?.cancel()
                animator = ValueAnimator.ofFloat(0.3f, 1f).apply {
                    duration = 1000
                    repeatMode = ValueAnimator.REVERSE
                    repeatCount = ValueAnimator.INFINITE
                    addUpdateListener {
                        val a = (it.animatedValue as Float * 255).toInt()
                        tv.setTextColor(ColorUtils.setAlphaComponent(base, a))
                    }
                    start()
                }
                tv.text = "결과 생성 중 입니다..."
            }
        }

        fun sendChatRequest(userMessage: String, onChunk: (String) -> Unit) {
            CoroutineScope(Dispatchers.IO).launch {
                val client = OkHttpClient.Builder() //소켓타임아웃방지코드
                    .connectTimeout(30, TimeUnit.SECONDS)  // 연결 타임아웃 30초
                    .readTimeout(0, TimeUnit.SECONDS)      // 스트리밍 응답 무제한 대기 (중요!)
                    .writeTimeout(30, TimeUnit.SECONDS)    // 쓰기 타임아웃 30초
                    .build()

                val body = JSONObject().put("message", userMessage).toString()
                    .toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())
                val req = Request.Builder()
                    .url("http://54.252.159.52:5000/stream-chat")
                    .post(body)
                    .build()
                try {
                    client.newCall(req).execute().use { resp ->
                        if (!resp.isSuccessful) return@use onChunk("Error: ${resp.code}")
                        val src = resp.body?.source() ?: return@use onChunk("Error: null body")
                        while (src.request(1)) {
                            val chunk = src.buffer.readUtf8(minOf(1024L, src.buffer.size))
                            withContext(Dispatchers.Main) { onChunk(chunk) }
                        }
                    }
                } catch (e: Exception) {
                    withContext(Dispatchers.Main) { onChunk("Stream Error: ${e.message}") }
                }
            }
        }
    }

    private fun updateEntryList() {
        val list = easyCommandMap[currentCategory]?.map {
            val parts = it.split(":")
            parts[0] to parts.getOrNull(1).orEmpty()
        }?.toMutableList() ?: mutableListOf()
        list.add("+" to "")
        entryAdapter.updateList(list)
    }

    private fun refreshCategoryAdapter() {
        categoryAdapter = EasyCommandCategoryAdapter(
            easyCommandMap.keys.toList(),
            categoryAdapter.onCategoryClick,
            categoryAdapter.onDeleteConfirmed
        ).apply { setOnAddCategoryClickListener { showAddCategoryDialog() } }
        recyclerCategory.adapter = categoryAdapter
        updateEntryList()
    }

    private fun showAddCategoryDialog() {
        val input = EditText(this)
        AlertDialog.Builder(this)
            .setTitle("카테고리 추가")
            .setView(input)
            .setPositiveButton("추가") { _, _ ->
                val name = input.text.toString().trim()
                if (name.isNotBlank() && !easyCommandMap.containsKey(name)) {
                    easyCommandMap[name] = mutableListOf()
                    refreshCategoryAdapter()
                }
            }
            .setNegativeButton("취소", null)
            .show()
    }

    private fun openDetail(title: String?, prompt: String?) {
        CommandDetailFragment.newInstance(currentCategory, title, prompt)
            .show(supportFragmentManager, "CommandDetail")
    }


    private fun measureViewHeight(view: View): Int {
        val widthSpec = View.MeasureSpec.makeMeasureSpec(view.width, View.MeasureSpec.EXACTLY)
        val heightSpec = View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED)
        view.measure(widthSpec, heightSpec)
        return view.measuredHeight
    }

    private fun showEasyCommandLists() {
        if (isEasyCommandVisible) return
        isEasyCommandVisible = true

        recyclerEasyCommand.visibility = View.VISIBLE
        recyclerCommandEntry.visibility = View.VISIBLE

        recyclerEasyCommand.viewTreeObserver.addOnGlobalLayoutListener(object : ViewTreeObserver.OnGlobalLayoutListener {
            override fun onGlobalLayout() {
                recyclerEasyCommand.viewTreeObserver.removeOnGlobalLayoutListener(this)
                recyclerCommandEntry.viewTreeObserver.addOnGlobalLayoutListener(object : ViewTreeObserver.OnGlobalLayoutListener {
                    override fun onGlobalLayout() {
                        recyclerCommandEntry.viewTreeObserver.removeOnGlobalLayoutListener(this)
                        adjustInputAreaForEasyCommand(true)
                    }
                })
            }
        })
    }



    private fun hideEasyCommandLists() {
        if (!isEasyCommandVisible) return  // 이미 꺼져 있으면 실행 안 함
        isEasyCommandVisible = false

        recyclerEasyCommand.visibility = View.GONE
        recyclerCommandEntry.visibility = View.GONE
        adjustInputAreaForEasyCommand(false)
    }

    private fun toggleEasyCommand() {
        if (isEasyCommandVisible) {
            hideEasyCommandLists()
        } else {
            showEasyCommandLists()
        }
    }



    private fun setupKeyboardListener() {
        val rootView = findViewById<View>(android.R.id.content)
        rootView.viewTreeObserver.addOnGlobalLayoutListener {
            val rect = Rect()
            rootView.getWindowVisibleDisplayFrame(rect)
            val screenHeight = rootView.rootView.height
            val keypadHeight = screenHeight - rect.bottom

            if (keypadHeight > screenHeight * 0.15) {
                // 키보드가 올라간 상태
                Log.d("Keyboard", "키보드 올라감")
            } else {
                // 키보드 내려간 상태
                Log.d("Keyboard", "키보드 내려감")
                if (isEasyCommandVisible) {
                    // 마진이 남아있으면 기본값으로 초기화
                    adjustInputAreaForEasyCommand(false)
                }
            }
        }
    }




    private fun dpToPx(dp: Int): Int {
        return (dp * resources.displayMetrics.density).toInt()
    }

//    private fun adjustInputAreaForEasyCommand(show: Boolean) {
//        val params = inputArea.layoutParams as ViewGroup.MarginLayoutParams
//        if (show) {
//            val easyHeight = recyclerEasyCommand.height + recyclerCommandEntry.height + dpToPx(20)
//            Log.d("AdjustInputArea", "recyclerEasyCommand.height = ${recyclerEasyCommand.height}, recyclerCommandEntry.height = ${recyclerCommandEntry.height}, easyHeight = $easyHeight")
//            params.bottomMargin = easyHeight
//        } else {
//            params.bottomMargin = dpToPx(10)
//            Log.d("AdjustInputArea", "Set bottomMargin to default ${dpToPx(10)}")
//        }
//        inputArea.layoutParams = params
//        inputArea.requestLayout()
//    }

    private fun adjustInputAreaForEasyCommand(show: Boolean) {
        val params = inputArea.layoutParams as ViewGroup.MarginLayoutParams
        val desiredMargin = if (show) {
            // 두 리사이클러뷰 높이 합 + 여유 마진(dpToPx)
            recyclerEasyCommand.height + recyclerCommandEntry.height + dpToPx(16)
        } else {
            dpToPx(10)
        }

        if (params.bottomMargin != desiredMargin) {
            params.bottomMargin = desiredMargin
            inputArea.layoutParams = params
            inputArea.requestLayout()
            Log.d("AdjustInputArea", "Set bottomMargin to $desiredMargin")
        } else {
            Log.d("AdjustInputArea", "bottomMargin already set to $desiredMargin, skip")
        }
    }

    companion object {
        fun newInstance(): FieldChatActivity = FieldChatActivity()
    }

//    override fun onBackPressed() {
//        if (recyclerEasyCommand.visibility == View.VISIBLE || recyclerCommandEntry.visibility == View.VISIBLE) {
//            hideEasyCommandLists() // 뷰 숨기고 inputArea 조절
//        } else if (fragmentContainer.visibility == View.VISIBLE) {
//            supportFragmentManager.popBackStack()
//            fragmentContainer.visibility = View.GONE
//            chatContainer.visibility = View.VISIBLE
//        } else {
//            super.onBackPressed()
//        }
//    }

    override fun onBackPressed() {
        if (isEasyCommandVisible) {
            hideEasyCommandLists()
        } else if (fragmentContainer.visibility == View.VISIBLE) {
            supportFragmentManager.popBackStack()
            fragmentContainer.visibility = View.GONE
            chatContainer.visibility = View.VISIBLE
        } else {
            super.onBackPressed()
        }
    }

//    override fun onBackPressed() {
//        if (fragmentContainer.visibility == View.VISIBLE) {
//            supportFragmentManager.popBackStack()
//            fragmentContainer.visibility = View.GONE
//            chatContainer.visibility     = View.VISIBLE
//
//            recyclerEasyCommand.visibility = View.GONE
//            recyclerCommandEntry.visibility = View.GONE
//        } else {
//            super.onBackPressed()
//        }
//    }

//    override fun dispatchTouchEvent(ev: MotionEvent): Boolean {
//        if (ev.action == MotionEvent.ACTION_DOWN) {
//            // ▶ 터치 위치 계산
//            val x = ev.rawX.toInt()
//            val y = ev.rawY.toInt()
//            // EditText, 카테고리, 엔트리 영역 Rect
//            val editRect = Rect().apply { messageEditText.getGlobalVisibleRect(this) }
//            val catRect  = Rect().apply { recyclerCategory.getGlobalVisibleRect(this) }
//            val entRect  = Rect().apply { recyclerEntry.getGlobalVisibleRect(this) }
//            // 이 영역들 외부 클릭 시에만 포커스 해제
//            if (!editRect.contains(x, y) && !catRect.contains(x, y) && !entRect.contains(x, y)) {
//                currentFocus?.clearFocus()
//                }
//        }
//        return super.dispatchTouchEvent(ev)
//    }


    override fun dispatchTouchEvent(ev: MotionEvent): Boolean {
        if (ev.action == MotionEvent.ACTION_DOWN) {
            val x = ev.rawX.toInt()
            val y = ev.rawY.toInt()

            val easyCmdRect = Rect().apply { recyclerEasyCommand.getGlobalVisibleRect(this) }
            val cmdEntryRect = Rect().apply { recyclerCommandEntry.getGlobalVisibleRect(this) }
            val plusBtnRect = Rect().apply { btnPlus.getGlobalVisibleRect(this) }

            // 리스트 외 클릭 시 닫기
            if ((recyclerEasyCommand.visibility == View.VISIBLE || recyclerCommandEntry.visibility == View.VISIBLE)
                && !easyCmdRect.contains(x, y)
                && !cmdEntryRect.contains(x, y)
                && !plusBtnRect.contains(x, y)) {
                recyclerEasyCommand.visibility = View.GONE
                recyclerCommandEntry.visibility = View.GONE
                adjustInputAreaForEasyCommand(false)
                currentFocus?.clearFocus()
            }
        }
        return super.dispatchTouchEvent(ev)
    }

}
