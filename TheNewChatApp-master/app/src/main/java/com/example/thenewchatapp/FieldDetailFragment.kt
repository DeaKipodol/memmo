package com.example.thenewchatapp

import android.content.Intent
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.*
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.ImageButton
import androidx.appcompat.widget.PopupMenu
import android.widget.Toast
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import android.view.Gravity
import android.widget.ArrayAdapter
import android.widget.ListPopupWindow

class FieldDetailFragment : Fragment(R.layout.fragment_field_detail) {

    private lateinit var editTextTitle: EditText
    private lateinit var editTextContent: EditText
    private lateinit var btnVoice: ImageButton
    private lateinit var btnPlus: ImageButton
    private val viewModel: FieldViewModel by activityViewModels()
    private lateinit var fragmentContainer: FrameLayout

    // arguments 로 넘어온 필드 제목/내용
    private var titleArg: String = ""
    private var contentArg: String = ""

    companion object {
        private const val ARG_TITLE = "title"
        private const val ARG_CONTENT = "content"

        fun newInstance(title: String, content: String): FieldDetailFragment {
            return FieldDetailFragment().apply {
                arguments = Bundle().apply {
                    putString(ARG_TITLE, title)
                    putString(ARG_CONTENT, content)
                }
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        arguments?.let {
            titleArg   = it.getString(ARG_TITLE, "")
            contentArg = it.getString(ARG_CONTENT, "")
        }
    }

    private val fieldKeys = listOf(
        "목적","주제","독자","형식 혹은 구조",
        "근거자료","어조","분량, 문체, 금지어 등","추가사항"
    )

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {

        super.onViewCreated(view, savedInstanceState)

        editTextTitle   = view.findViewById(R.id.editTextTitle)
        editTextContent = view.findViewById(R.id.editTextContent)
        btnVoice        = view.findViewById(R.id.btnVoice)
        btnPlus         = view.findViewById(R.id.btnPlus)
        fragmentContainer = view.findViewById(R.id.fragmentContainer)

        // 제목/내용 초기화
        editTextTitle.setText(titleArg)
        editTextContent.setText(contentArg)

        // 2) 제목 초기화: ViewModel에 저장된 값이 있으면 그걸, 없으면 fieldKey 그대로
        val initialTitle = viewModel.getTitle(titleArg).ifEmpty { titleArg }
        editTextTitle.setText(initialTitle)

        // 3) 내용 초기화
        val initialContent = viewModel.getContent(titleArg)
        editTextContent.setText(initialContent)

        // 1) fieldKey 가져오기
        val fieldKey = arguments?.getString(ARG_TITLE) ?: ""

        // 2) ViewModel 에서 이전에 저장된 값 불러오기
        editTextTitle.setText(viewModel.getTitle(fieldKey))
        editTextContent.setText(viewModel.getContent(fieldKey))

        // 3) 변경될 때마다 ViewModel에 저장
        editTextTitle.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) {
                viewModel.setTitle(titleArg, s.toString())
            }
            override fun beforeTextChanged(s: CharSequence?, st: Int, c: Int, a: Int) = Unit
            override fun onTextChanged(s: CharSequence?, st: Int, b: Int, c: Int) = Unit
        })

        editTextContent.setText(viewModel.getContent(titleArg))

        editTextContent.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) {
                viewModel.setContent(fieldKey, s.toString())
            }
            override fun beforeTextChanged(s: CharSequence?, st: Int, c: Int, a: Int) = Unit
            override fun onTextChanged(s: CharSequence?, st: Int, b: Int, c: Int) = Unit
        })

        // + 버튼 팝업 (챗봇 / 글 정리)
        btnPlus.setOnClickListener { anchor ->
            val listPopupWindow = ListPopupWindow(requireContext(), null, android.R.attr.listPopupWindowStyle)

            // 메뉴 아이템 설정
            val items = listOf("챗봇", "글 정리")
            val adapter = ArrayAdapter(requireContext(), android.R.layout.simple_list_item_1, items)
            listPopupWindow.setAdapter(adapter)

            // 앵커 뷰 설정 (팝업이 뜰 기준 뷰)
            listPopupWindow.anchorView = anchor

            // 팝업창의 너비 설정 (옵션)
            listPopupWindow.setContentWidth(500) // 예시: 300px 또는 WRAP_CONTENT 등

            // 메뉴 아이템 클릭 리스너 설정
            listPopupWindow.setOnItemClickListener { _, _, position, _ ->
                val selectedItem = items[position]
                when (selectedItem) {
                    "챗봇" -> {
                        val intent = Intent(requireActivity(), FieldChatActivity::class.java)
                        startActivity(intent)
                    }
                    "글 정리" -> {
                        Toast.makeText(
                            requireContext(),
                            "$selectedItem 기능은 추후 추가됩니다.",
                            Toast.LENGTH_SHORT
                        ).show()
                    }
                }
                listPopupWindow.dismiss() // 메뉴 선택 후 팝업 닫기
            }

            // 팝업 위치를 버튼 위로 조정
            // ListPopupWindow는 기본적으로 앵커 뷰 아래에 표시됩니다.
            // verticalOffset을 음수 값으로 설정하여 위로 올립니다.
            // 정확히 버튼 위에 위치시키려면 (앵커 뷰 높이 + 팝업창 자체의 높이) 만큼 올려야 합니다.
            anchor.post { // 앵커 뷰의 높이를 정확히 가져오기 위해 post 사용
                // 팝업창 내용의 높이를 계산 (아이템 개수 * 아이템 당 예상 높이)
                // 실제 아이템 뷰를 측정하는 것이 가장 정확하지만, 여기서는 간이 계산법을 사용합니다.
                val density = requireContext().resources.displayMetrics.density
                val estimatedItemHeight = (48 * density).toInt() // 일반적인 아이템 높이 48dp
                val popupContentHeight = estimatedItemHeight * adapter.count

                listPopupWindow.verticalOffset = -(anchor.height + popupContentHeight)
                listPopupWindow.show()
            }
        }

        // 포커스 잃으면 제목/내용 저장
        editTextTitle.setOnFocusChangeListener { _, has ->
            if (!has) savedFieldTitles[titleArg] = editTextTitle.text.toString()
        }
        editTextContent.setOnFocusChangeListener { _, has ->
            if (!has) savedFieldContents[titleArg] = editTextContent.text.toString()
        }
    }

    // 임시 저장용 맵 (fragment-wide)
    private val savedFieldTitles   = mutableMapOf<String, String>()
    private val savedFieldContents = mutableMapOf<String, String>()
}
