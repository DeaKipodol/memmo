// ✅ 팝업 제거 및 하단 바 중심으로 정리된 ListActivity.kt

package com.example.thenewchatapp

import android.content.Intent
import android.content.SharedPreferences
import android.os.Bundle
import android.view.MotionEvent
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.app.AppCompatDelegate
import androidx.recyclerview.widget.GridLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.floatingactionbutton.ExtendedFloatingActionButton
import java.io.File

class ListActivity : AppCompatActivity() {

    private lateinit var recyclerView: RecyclerView
    private lateinit var listAdapter: ListAdapter
    private lateinit var createButton: ExtendedFloatingActionButton
    private lateinit var fabField: ExtendedFloatingActionButton
    private lateinit var fabWrite: ExtendedFloatingActionButton
    private lateinit var fabChat: ExtendedFloatingActionButton
    private lateinit var bottomBar: LinearLayout
    private lateinit var buttonRename: TextView
    private lateinit var buttonDelete: TextView
    private lateinit var btnThemeToggle: Button
    private lateinit var prefs: SharedPreferences

    private var isFabOpen = false

    override fun onCreate(savedInstanceState: Bundle?) {
        // ▶ ① 테마 설정 불러와 적용
        prefs = getSharedPreferences("settings", MODE_PRIVATE)
        AppCompatDelegate.setDefaultNightMode(
            prefs.getInt("theme_mode", AppCompatDelegate.MODE_NIGHT_FOLLOW_SYSTEM)
        )

        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_list)

        recyclerView = findViewById(R.id.recyclerView)
        recyclerView.layoutManager = GridLayoutManager(this, 2)

        createButton = findViewById(R.id.buttonCreateDocument)
        fabField = findViewById(R.id.fab_field)
        fabWrite = findViewById(R.id.fab_write)
        fabChat = findViewById(R.id.fab_chat)

        bottomBar = findViewById(R.id.bottomBar)
        buttonRename = findViewById(R.id.buttonRename)
        buttonDelete = findViewById(R.id.buttonDelete)
        btnThemeToggle = findViewById(R.id.btnThemeToggle)



        recyclerView = findViewById(R.id.recyclerView)
        recyclerView.layoutManager = GridLayoutManager(this, 2)

        val iconMenu = findViewById<ImageView>(R.id.icon_menu)
        val iconSearch = findViewById<ImageView>(R.id.icon_search)
        val iconMore = findViewById<ImageView>(R.id.icon_more)

        val clearSelectionClickListener = View.OnClickListener {
            clearSelectionAndHideBar()
        }

        val logoContainer = findViewById<View>(R.id.logoContainer)
        val iconBar = findViewById<View>(R.id.iconBar)

        iconMenu.setOnClickListener {
            Toast.makeText(this, "햄버거 메뉴 클릭됨", Toast.LENGTH_SHORT).show()
        }

        iconSearch.setOnClickListener {
            Toast.makeText(this, "검색 클릭됨", Toast.LENGTH_SHORT).show()
        }

        iconMore.setOnClickListener {
            Toast.makeText(this, "더보기 클릭됨", Toast.LENGTH_SHORT).show()
        }

        createButton.setOnClickListener {
            toggleFabMenu()
        }

        fabField.setOnClickListener {
            toggleFabMenu()
            startActivity(Intent(this, FieldActivity::class.java))
        }

        fabWrite.setOnClickListener {
            toggleFabMenu()
            startActivity(Intent(this, MainActivity::class.java))
        }

        fabChat.setOnClickListener {
            toggleFabMenu()
            startActivity(Intent(this, ChatActivity::class.java))
        }

        loadDocumentsAndCreateAdapter()

        buttonRename.setOnClickListener {
            val selected = listAdapter.getSelectedItems()
            if (selected.size == 1) {
                showRenameDialog(selected.first())
            }
        }

        buttonDelete.setOnClickListener {
            val selected = listAdapter.getSelectedItems()
            if (selected.isNotEmpty()) {
                showDeleteDialog(selected)
            }
        }
        
        btnThemeToggle.setOnClickListener {
            val current = AppCompatDelegate.getDefaultNightMode()
            val next = if (current == AppCompatDelegate.MODE_NIGHT_YES)
                AppCompatDelegate.MODE_NIGHT_NO
            else
                AppCompatDelegate.MODE_NIGHT_YES

            // ▶ ③ 저장 & 적용 & 재시작
            prefs.edit().putInt("theme_mode", next).apply()
            AppCompatDelegate.setDefaultNightMode(next)
            recreate()
        }


        recyclerView.setOnTouchListener { v, event ->
            if (event.action == MotionEvent.ACTION_DOWN) {
                val child = recyclerView.findChildViewUnder(event.x, event.y)
                if (child == null && listAdapter.getSelectedItems().isNotEmpty()) {
                    listAdapter.clearSelection()
                    bottomBar.visibility = View.GONE
                    createButton.visibility = View.VISIBLE
                }
            }
            false
        }


        // RecyclerView 외부 영역 터치 시 선택 해제 처리
        val rootLayout = findViewById<View>(android.R.id.content)
        rootLayout.setOnTouchListener { v, event ->
            // 선택 상태가 있으면 해제 및 하단 바 숨김
            if (listAdapter.getSelectedItems().isNotEmpty()) {
                listAdapter.clearSelection()
                bottomBar.visibility = View.GONE
                createButton.visibility = View.VISIBLE
            }
            false  // 이벤트 소비하지 않음, 다른 터치 이벤트는 정상 처리
        }


        logoContainer.setOnClickListener(clearSelectionClickListener)
        iconBar.setOnClickListener(clearSelectionClickListener)
        iconMenu.setOnClickListener(clearSelectionClickListener)
        iconSearch.setOnClickListener(clearSelectionClickListener)
        iconMore.setOnClickListener(clearSelectionClickListener)





    }

    private fun clearSelectionAndHideBar() {
        if (listAdapter.getSelectedItems().isNotEmpty()) {
            listAdapter.clearSelection()
            bottomBar.visibility = View.GONE
            createButton.visibility = View.VISIBLE
        }
    }


    private fun toggleFabMenu() {
        if (isFabOpen) {
            fabWrite.hide()
            fabChat.hide()
            fabField.hide()
            createButton.animate().rotation(0f).setDuration(200).start()
        } else {
            fabWrite.show()
            fabChat.show()
            fabField.show()
            createButton.animate().rotation(45f).setDuration(200).start()
        }
        isFabOpen = !isFabOpen
    }

    override fun onBackPressed() {
        when {
            isFabOpen -> toggleFabMenu()
            listAdapter.getSelectedItems().isNotEmpty() -> {
                listAdapter.clearSelection()
                bottomBar.visibility = View.GONE
                createButton.visibility = View.VISIBLE
            }
            else -> super.onBackPressed()
        }
    }

    override fun onResume() {
        super.onResume()
        loadDocumentsAndCreateAdapter()
    }

    private fun loadDocumentsAndCreateAdapter() {
        val documentList = loadDocuments().map { file -> file.name }

        listAdapter = ListAdapter(
            documentList,
            onItemClick = { fileName ->
                openDocument(fileName)
            },
            onSelectionChanged = { selectedDocs ->
                bottomBar.visibility = if (selectedDocs.isNotEmpty()) View.VISIBLE else View.GONE
                createButton.visibility = if (selectedDocs.isNotEmpty()) View.GONE else View.VISIBLE
            }
        )

        recyclerView.adapter = listAdapter
    }

    private fun loadDocuments(): List<File> {
        return filesDir.listFiles()?.filter {
            it.name.endsWith(".mdocx")
        }?.sortedByDescending { it.lastModified() } ?: emptyList()
    }

    private fun openDocument(fileName: String) {
        val intent = Intent(this, MainActivity::class.java)
        intent.putExtra("fileName", fileName)
        startActivity(intent)
    }

    private fun showRenameDialog(fileName: String) {
        val editText = EditText(this)

        // 확장자 뗀 순수 제목 얻기
        val pureTitle = fileName.removeSuffix(".mdocx")

        // 자동제목 패턴 (예: "텍스트 노트 0512_154530")
        val autoTitlePattern = Regex("""^텍스트 노트 \d{4}_\d{6}$""")

        // 자동제목이면 빈 문자열, 아니면 기존 제목 세팅
        val initialTitle = if (autoTitlePattern.matches(pureTitle)) {
            ""  // 자동 제목일 때 빈 문자열 세팅
        } else {
            pureTitle
        }



        editText.setText(initialTitle)

        AlertDialog.Builder(this)
            .setTitle("제목 수정")
            .setView(editText)
            .setPositiveButton("확인") { _, _ ->
                val newName = editText.text.toString().trim()
                if (newName.isNotEmpty()) {
                    val file = File(filesDir, fileName)
                    val newFile = File(filesDir, "$newName.mdocx")
                    file.renameTo(newFile)
                    loadDocumentsAndCreateAdapter()
                }
            }
            .setNegativeButton("취소", null)
            .show()
    }


    private fun showDeleteDialog(selected: List<String>) {
        AlertDialog.Builder(this)
            .setTitle("삭제")
            .setMessage("정말 삭제하시겠습니까?")
            .setPositiveButton("삭제") { _, _ ->
                selected.forEach {
                    val file = File(filesDir, it)
                    if (file.exists()) file.delete()
                }
                loadDocumentsAndCreateAdapter()
            }
            .setNegativeButton("취소", null)
            .show()
    }
}
