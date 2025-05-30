/*
 * Project: TheNewChatApp
 * Version: 4.0.1
 * Last updated: 2025-05-30 09:00
 * Author: SiHyeon Cheon
 *
 * [Description]
8필드, 이지커맨드 통합, 제목 저장관련 수정
 */

package com.example.thenewchatapp

import android.content.Intent
import android.content.SharedPreferences
import android.os.Bundle
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.app.AppCompatDelegate
import java.io.File
import java.text.SimpleDateFormat
import java.util.*
import android.widget.Toast
import android.widget.PopupMenu

class MainActivity : AppCompatActivity() {

    private lateinit var titleEditText: EditText
    private lateinit var editText: EditText
    private lateinit var backButton: ImageButton
    private lateinit var textViewContent: EditText
    private lateinit var btnVoice: ImageButton
    private lateinit var btnPlus: ImageButton
    private lateinit var fragmentContainer: FrameLayout

    private val customExtension = ".mdocx"
    private var currentFileName: String? = null

    companion object {
        lateinit var prefs: SharedPreferences
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        prefs = getSharedPreferences("settings", MODE_PRIVATE)
        AppCompatDelegate.setDefaultNightMode(
            prefs.getInt("theme_mode", AppCompatDelegate.MODE_NIGHT_FOLLOW_SYSTEM)
        )

        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        titleEditText = findViewById(R.id.titleEditText)
        editText = findViewById(R.id.editText)
        backButton = findViewById(R.id.backButton)

        // 챗봇 답변 내용 편집을 메인엑티비티로 변경했을 때 쓰이는 코드
        // EditText 초기화 이후 onCreate 안에 추가
        intent.getStringExtra("originalText")?.let { originalText ->
            editText.setText(originalText)
        }

        val isFromChat = intent.hasExtra("messagePosition")

        backButton.setOnClickListener {
            onBackPressed()  // ✅ 시스템 뒤로가기처럼 자동 저장 후 finish()까지 작동
        }

        val fileName = intent.getStringExtra("fileName")
        if (!fileName.isNullOrEmpty()) {
            val file = File(filesDir, fileName)
            if (file.exists()) {
                val pureTitle = file.name.removeSuffix(customExtension).substringBefore("_")
                if (!pureTitle.startsWith("텍스트 노트 ")) {
                    titleEditText.setText(pureTitle)
                }
                editText.setText(file.readText())
                currentFileName = fileName
            }
        }

        btnVoice = findViewById(R.id.btnVoice)
        btnPlus = findViewById(R.id.btnPlus)
        fragmentContainer = findViewById(R.id.fragmentContainer)

        btnPlus.setOnClickListener {
            PopupMenu(this, it).apply {
                menu.add("챗봇").setOnMenuItemClickListener {
                    startActivity(Intent(this@MainActivity, ChatActivity::class.java))
                    true
                }
                menu.add("요구사항").setOnMenuItemClickListener {
                    startActivity(Intent(this@MainActivity, FieldActivity::class.java))
                    true
                }
                show()
            }
        }

        btnVoice.setOnClickListener {
            Toast.makeText(
                this,  // Activity 자체를 Context로 사용
                "음성 인식이 시작됩니다.",
                Toast.LENGTH_SHORT
            ).show()
        }
    }

    override fun onBackPressed() {
        saveIfNeeded(forceSave = false)
        super.onBackPressed()
    }

    private fun saveIfNeeded(forceSave: Boolean = false) {
        val content = editText.text.toString().trim()
        if (content.isEmpty() && !forceSave) {
            Toast.makeText(this, "입력한 내용이 없어 저장하지 않았습니다.", Toast.LENGTH_SHORT).show()
            return
        }

        val inputTitle = titleEditText.text.toString().trim()
        val currentTime = Date()

        // 이전 파일명 (현재 저장 중인 파일명)
        val oldFileName = currentFileName

        // 새 파일명 생성
        val newFileName = when {
            oldFileName != null -> {
                // 제목이 변경되었으면 새 파일명 생성
                val oldTitle = oldFileName.removeSuffix(customExtension)
                if (inputTitle.isNotEmpty() && inputTitle != oldTitle) {
                    "$inputTitle$customExtension"
                } else {
                    oldFileName
                }
            }
            inputTitle.isNotEmpty() -> inputTitle + customExtension
            else -> "텍스트 노트 " + SimpleDateFormat("MMdd_HHmmss", Locale.getDefault()).format(currentTime) + customExtension
        }

        // 파일 rename 처리 (기존 파일이 있고 이름이 변경되었으면)
        if (oldFileName != null && oldFileName != newFileName) {
            val oldFile = File(filesDir, oldFileName)
            val newFile = File(filesDir, newFileName)

            if (newFile.exists()) {
                Toast.makeText(this, "같은 이름의 파일이 이미 존재합니다.", Toast.LENGTH_SHORT).show()
                return
            }

            val renamed = oldFile.renameTo(newFile)
            if (!renamed) {
                Toast.makeText(this, "파일명 변경에 실패했습니다.", Toast.LENGTH_SHORT).show()
                return
            }
            currentFileName = newFileName
        } else if (oldFileName == null) {
            currentFileName = newFileName
        }

        // 내용 저장
        val file = File(filesDir, currentFileName!!)
        file.writeText(content)

        Toast.makeText(this, "저장되었습니다", Toast.LENGTH_SHORT).show()
    }


}
