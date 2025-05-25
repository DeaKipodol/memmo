import sys
import os
import pytest
import logging
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from ai_app.chatbotStream import ChatbotStream
from main import app
from ai_app.assist.ConversationContextFactory import ConversationContextFactory

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler("chatbot_test.log")]
)
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("fastapi").setLevel(logging.WARNING)
logger = logging.getLogger("chatbot_tests")

# 경로 설정
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 모듈 임포트
from ai_app.assist.common import model
from ai_app.utils.writingRequirementsManager import WritingRequirementsManager
from ai_app.utils.function_calling import FunctionCalling, tools

# FastAPI 테스트 클라이언트
test_client = TestClient(app)

# 픽스처: 테스트용 챗봇 인스턴스
@pytest.fixture
def chatbot():
    logger.info("테스트용 ChatbotStream 인스턴스 생성")
    return ChatbotStream(model="basic", system_role="test", instruction="", user="test", assistant="test")

# 픽스처: 임시 데이터 설정
@pytest.fixture(autouse=True)
def setup_test_data(chatbot, monkeypatch):
    logger.debug("임시 데이터 설정 시작")
    chatbot.writingRequirementsManager.writing_requirements["purpose_background"] = "글쓰기 목적은 사용자를 돕는 것입니다."
    chatbot.writingRequirementsManager.writing_requirements["context_topic"] = "주제는 인공지능의 발전입니다."
    monkeypatch.setattr('main.chatbot', chatbot)
    logger.debug("임시 데이터 설정 완료")
    return chatbot

# 픽스처: GPT API 모킹
@pytest.fixture
def mock_api():
    with patch('ai_app.assist.common.client.responses.create') as mock_create:
        def make_event(event_type, **kwargs):
            event = MagicMock()
            event.type = event_type
            for key, value in kwargs.items():
                setattr(event, key, value)
            return event

        events = [
            make_event("response.created"),
            make_event("response.output_text.delta", delta="모의 "),
            make_event("response.output_text.delta", delta="응답 텍스트"),
            make_event(
                "response.output_item.done",
                item=MagicMock(
                    type="message",
                    role="assistant",
                    content=[MagicMock(type="output_text", text="모의 응답 텍스트")]
                )
            ),
            make_event("response.completed")
        ]
        mock_response = MagicMock()
        mock_response.output_text = "요약된 내용"
        mock_create.side_effect = [events, mock_response]  # GPT 호출과 요약 호출 분리
        yield mock_create

# 단위 테스트: 서브 대화방 메시지 추가
def test_add_user_message_sub_context(chatbot):
    logger.info("테스트 시작: 서브 대화방에 메시지 추가")
    chatbot.enter_sub_conversation("purpose_background")
    chatbot.add_user_message_in_context("서브 테스트 메시지")
    assert len(chatbot.sub_contexts["purpose_background"]["messages"]) == 1
    assert chatbot.sub_contexts["purpose_background"]["messages"][0] == {
        "role": "user",
        "content": "서브 테스트 메시지",
        "saved": False
    }
    logger.info("테스트 완료: 서브 대화방에 메시지 추가")

# 단위 테스트: 현재 문맥 가져오기
def test_get_current_context(chatbot):
    logger.info("테스트 시작: 현재 컨텍스트 가져오기")
    assert chatbot.get_current_context() is chatbot.context
    chatbot.enter_sub_conversation("purpose_background")
    assert chatbot.get_current_context() is chatbot.sub_contexts["purpose_background"]["messages"]
    logger.info("테스트 완료: 현재 컨텍스트 가져오기")

# 단위 테스트: 서브 대화방 진입
def test_enter_sub_conversation(chatbot):
    logger.info("테스트 시작: 서브 대화방 진입")
    result = chatbot.enter_sub_conversation("logic_evidence")
    assert chatbot.current_field == "logic_evidence"
    assert "logic_evidence" in chatbot.sub_contexts
    assert "messages" in chatbot.sub_contexts["logic_evidence"]
    assert "logic_evidence 에 대해" in result
    logger.info("테스트 완료: 서브 대화방 진입")

# 통합 테스트: 대화 흐름
def test_conversation_flow(chatbot, mock_api):
    logger.info("테스트 시작: 대화 흐름 (메인 -> 서브 -> 메인)")
    chatbot.add_user_message_in_context("메인 메시지")
    assert len(chatbot.context) > 0
    assert chatbot.context[-1]["content"] == "메인 메시지"
    chatbot.enter_sub_conversation("purpose_background")
    chatbot.add_user_message_in_context("서브 메시지")
    assert len(chatbot.sub_contexts["purpose_background"]["messages"]) == 1
    assert chatbot.sub_contexts["purpose_background"]["messages"][0]["content"] == "서브 메시지"
    with patch.object(chatbot, 'writingRequirementsManager') as mock_manager:
        mock_manager.update_field.return_value = "필드 업데이트 완료"
        result = chatbot.exit_sub_conversation()
    assert chatbot.current_field == "main"
    assert mock_manager.update_field.called
    logger.info(f"테스트 완료: 대화 흐름 (결과: {result})")

# 통합 테스트: GPT 응답 생성
def test_gpt_response(chatbot, mock_api):
    logger.info("테스트 시작: GPT 응답 생성")
    chatbot.add_user_message_in_context("테스트 질문")
    response = chatbot._send_request_Stream()
    assert mock_api.called
    assert response == "모의 응답 텍스트"
    logger.info(f"테스트 완료: GPT 응답 생성 (응답: {response})")

# 통합 테스트: 예외 처리
def test_exception_handling(chatbot):
    logger.info("테스트 시작: 예외 처리")
    try:
        chatbot.current_field = "non_existent_field"
        chatbot.get_current_context()
        assert False, "예외가 발생해야 합니다."
    except Exception as e:
        logger.info(f"예상된 예외 발생: {e}")
    logger.info("테스트 완료: 예외 처리")

# 단위 테스트: GET /field-content/{field_name}
def test_get_field_content(setup_test_data):
    logger.info("테스트 시작: GET /field-content/{field_name}")
    test_cases = [
        (
            "purpose_background",
            "'purpose_background' 필드 내용:\n글쓰기 목적은 사용자를 돕는 것입니다.",
            "purpose_background 필드의 내용을 반환했습니다."
        ),
        (
            "context_topic",
            "'context_topic' 필드 내용:\n주제는 인공지능의 발전입니다.",
            "context_topic 필드의 내용을 반환했습니다."
        )
    ]
    for field_name, expected_content, expected_message in test_cases:
        response = test_client.get(f"/field-content/{field_name}")
        assert response.status_code == 200
        json_response = response.json()
        assert json_response["success"] == True
        assert json_response["field_name"] == field_name
        assert json_response["content"] == expected_content
        assert json_response["message"] == expected_message
        logger.info(f"{field_name} 필드 테스트 성공")
    response = test_client.get("/field-content/invalid_field")
    assert response.status_code == 400
    assert response.json()["detail"] == "유효하지 않은 필드입니다."
    logger.info("유효하지 않은 필드 테스트 성공")

# 단위 테스트: GET /clarification-question/{field_name}
def test_get_clarification_question(setup_test_data):
    logger.info("테스트 시작: GET /clarification-question/{field_name}")
    chatbot = setup_test_data
    chatbot.sub_contexts["purpose_background"] = ConversationContextFactory.create_context("purpose_background")
    chatbot.sub_contexts["purpose_background"]["clarification_question"] = "글쓰기 목적을 구체화하려면 어떤 정보가 필요합니까?"
    
    response = test_client.get("/clarification-question/purpose_background")
    assert response.status_code == 200
    json_response = response.json()
    assert json_response["success"] == True
    assert json_response["field_name"] == "purpose_background"
    assert json_response["clarification_question"] == "글쓰기 목적을 구체화하려면 어떤 정보가 필요합니까?"
    assert json_response["message"] == "purpose_background의 clarification_question을 반환했습니다."
    
    response = test_client.get("/clarification-question/invalid_field")
    assert response.status_code == 400
    assert response.json()["detail"] == "유효하지 않은 서브 대화방입니다."
    logger.info("테스트 완료: GET /clarification-question/{field_name}")

# 단위 테스트: POST /update-field
def test_update_field(setup_test_data, mock_api):
    logger.info("테스트 시작: POST /update-field")
    chatbot = setup_test_data
    chatbot.sub_contexts["context_topic"] = ConversationContextFactory.create_context("context_topic")
    
    response = test_client.post("/update-field", json={
        "field_name": "context_topic",
        "content": "새로운 주제: AI 윤리"
    })
    assert response.status_code == 200
    json_response = response.json()
    assert json_response["success"] == True
    assert json_response["field_name"] == "context_topic"
    assert "새로운 주제: AI 윤리" in json_response["content"]
    assert json_response["clarification_question"]
    assert "context_topic 업데이트 및 요약 완료" in json_response["message"]
    
    response = test_client.post("/update-field", json={
        "field_name": "invalid_field",
        "content": "잘못된 내용"
    })
    assert response.status_code == 400
    assert response.json()["detail"] == "유효하지 않은 필드입니다."
    logger.info("테스트 완료: POST /update-field")

# 단위 테스트: POST /reset-conversation
def test_reset_conversation(setup_test_data):
    logger.info("테스트 시작: POST /reset-conversation")
    chatbot = setup_test_data
    chatbot.enter_sub_conversation("audience_scope")
    chatbot.add_user_message_in_context("독자 테스트")
    
    response = test_client.post("/reset-conversation")
    assert response.status_code == 200
    json_response = response.json()
    assert json_response["success"] == True
    assert json_response["message"] == "대화 상태가 초기화되었습니다."
    assert chatbot.current_field == "main"
    assert chatbot.sub_contexts == {}
    assert len(chatbot.context) == 1
    logger.info("테스트 완료: POST /reset-conversation")

# 통합 테스트: HTTP 요청으로 수동 테스트 시뮬레이션
def test_manual_conversation_flow(setup_test_data, mock_api):
    logger.info("테스트 시작: HTTP 요청으로 수동 대화 흐름")
    chatbot = setup_test_data
    
    # 1. 메인 대화방 메시지 전송
    response = test_client.post("/stream-chat", json={"message": "안녕하세요"})
    assert response.status_code == 200
    assert "모의 응답 텍스트" in response.text
    
    # 2. 서브 대화방 진입
    response = test_client.post("/enter-sub-conversation/purpose_background")
    assert response.status_code == 200
    assert "purpose_background 에 대해 도와드릴게요" in response.json()["message"]
    
    # 3. 서브 대화방 메시지 전송
    response = test_client.post("/stream-chat", json={"message": "글쓰기 목적은?"})
    assert response.status_code == 200
    assert "모의 응답 텍스트" in response.text
    
    # 4. 상태 확인
    response = test_client.get("/current-conversation")
    assert response.status_code == 200
    assert response.json()["current_field"] == "purpose_background"
    
    # 5. 필드 내용 조회
    response = test_client.get("/field-content/purpose_background")
    assert response.status_code == 200
    assert "글쓰기 목적은 사용자를 돕는 것입니다" in response.json()["content"]
    
    # 6. 요약 요청
    response = test_client.post("/stream-chat", json={"message": "요약"})
    assert response.status_code == 200
    assert "summary" in response.json()
    assert "title" in response.json()
    
    # 7. Clarification Question 조회
    chatbot.sub_contexts["purpose_background"]["clarification_question"] = "목적을 구체화하려면?"
    response = test_client.get("/clarification-question/purpose_background")
    assert response.status_code == 200
    assert response.json()["clarification_question"] == "목적을 구체화하려면?"
    
    # 8. 필드 내용 수정
    response = test_client.post("/update-field", json={
        "field_name": "context_topic",
        "content": "새로운 주제: AI 윤리"
    })
    assert response.status_code == 200
    assert "새로운 주제: AI 윤리" in response.json()["content"]
    
    # 9. 대화방 종료
    response = test_client.post("/exit-conversation")
    assert response.status_code == 200
    assert "이미 메인 대화방에 있습니다" not in response.json()["message"]
    
    # 10. 대화 초기화
    response = test_client.post("/reset-conversation")
    assert response.status_code == 200
    assert response.json()["message"] == "대화 상태가 초기화되었습니다."
    
    logger.info("테스트 완료: HTTP 요청으로 수동 대화 흐름")

# 통합 테스트: GPT API 실패 처리
def test_stream_chat_api_failure(setup_test_data):
    logger.info("테스트 시작: GPT API 실패 처리")
    with patch('ai_app.assist.common.client.responses.create', side_effect=Exception("API 오류")):
        response = test_client.post("/stream-chat", json={"message": "테스트"})
        assert response.status_code == 200
        assert "Stream Error: API 오류" in response.text
    logger.info("테스트 완료: GPT API 실패 처리")

if __name__ == "__main__":
    import requests  # HTTP 요청용
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [%(levelname)s] %(message)s',
        handlers=[logging.StreamHandler(), logging.FileHandler("chatbot_test.log")]
    )
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)
    
    print("===== Chatbot 수동 테스트 시작 =====")
    print("명령어: 종료, 입장 <필드>, 메인으로, 상태보기, 필드조회 <필드>, 요약, 질문조회 <필드>, 필드수정 <필드> <내용>, 또는 메시지")
    print("서버 URL: http://localhost:8000 (서버가 실행 중이어야 합니다)")
    
    # FastAPI 서버가 실행 중인 URL (로컬 테스트용)
    BASE_URL = "http://localhost:8000"
    
    while True:
        user_input = input("명령어 입력> ")
        if user_input.strip() == "종료":
            print("===== 수동 테스트 종료 =====")
            break

        try:
            if user_input.startswith("입장 "):
                field = user_input.replace("입장", "").strip()
                response = requests.post(f"{BASE_URL}/enter-sub-conversation/{field}")
                print(f"Response: {response.json()['message']}" if response.status_code == 200 else f"Error: {response.json()['detail']}")

            elif user_input == "메인으로":
                response = requests.post(f"{BASE_URL}/exit-conversation")
                print(f"Response: {response.json()['message']}" if response.status_code == 200 else f"Error: {response.json()['detail']}")

            elif user_input == "상태보기":
                try:
                    response = requests.get(f"{BASE_URL}/current-conversation")
                    if response.status_code == 200:
                        json_response = response.json()
                        current_field = json_response["current_field"]
                        print(f"📌 현재 필드: {current_field}")
                        print(f"📌 메시지: {json_response['message']}")
                        
                        # 대화 문맥 조회
                        response = requests.get(f"{BASE_URL}/conversation-history/{current_field}")
                        if response.status_code == 200:
                            history_response = response.json()
                            print(f"🗂️ {current_field} 문맥:")
                            for msg in history_response["history"]:
                                print(f"- [{msg['role']}] {msg['content']}")
                            print(f"🗂️ 문맥 길이: {len(history_response['history'])}")
                        else:
                            print(f"❌ 문맥 조회 실패: {response.json()['detail']}")
                    else:
                        print(f"❌ 상태 조회 실패: {response.json()['detail']}")
                except Exception as e:
                    print(f"❌ 요청 중 오류 발생: {e}")

            elif user_input.startswith("필드조회 "):
                field = user_input.replace("필드조회", "").strip()
                response = requests.get(f"{BASE_URL}/field-content/{field}")
                if response.status_code == 200:
                    json_response = response.json()
                    print(f"✅ 필드 조회 성공 ({field}):")
                    print(f"  - 내용: {json_response['content']}")
                    print(f"  - 메시지: {json_response['message']}")
                else:
                    print(f"❌ 필드 조회 실패 ({field}): {response.json()['detail']}")

            elif user_input == "요약":
                response = requests.post(f"{BASE_URL}/stream-chat", json={"message": "요약"})
                if response.status_code == 200:
                    json_response = response.json()
                    print(f"✅ 요약 성공:")
                    print(f"  - 요약: {json_response['summary']}")
                    print(f"  - 제목: {json_response['title']}")
                    print(f"  - 메시지: {json_response['message']}")
                else:
                    print(f"❌ 요약 실패: {response.json()['detail']}")

            elif user_input.startswith("질문조회 "):
                field = user_input.replace("질문조회", "").strip()
                response = requests.get(f"{BASE_URL}/clarification-question/{field}")
                if response.status_code == 200:
                    json_response = response.json()
                    print(f"✅ 질문 조회 성공 ({field}):")
                    print(f"  - 질문: {json_response['clarification_question']}")
                    print(f"  - 메시지: {json_response['message']}")
                else:
                    print(f"❌ 질문 조회 실패 ({field}): {response.json()['detail']}")

            elif user_input.startswith("필드수정 "):
                parts = user_input.replace("필드수정", "").strip().split(" ", 1)
                if len(parts) < 2:
                    print("❌ 필드수정 명령어 형식: 필드수정 <필드> <내용>")
                    continue
                field, content = parts
                response = requests.post(f"{BASE_URL}/update-field", json={
                    "field_name": field,
                    "content": content
                })
                if response.status_code == 200:
                    json_response = response.json()
                    print(f"✅ 필드 수정 성공 ({field}):")
                    print(f"  - 내용: {json_response['content']}")
                    print(f"  - 질문: {json_response['clarification_question']}")
                    print(f"  - 메시지: {json_response['message']}")
                else:
                    print(f"❌ 필드 수정 실패 ({field}): {response.json()['detail']}")

            else:
                response = requests.post(f"{BASE_URL}/stream-chat", json={"message": user_input})
                if response.status_code == 200:
                    print(f"💬 메시지 전송 성공: {user_input}")
                    print(f"🤖 응답: {response.text}")
                else:
                    print(f"❌ 메시지 전송 실패: {response.json()['detail']}")

        except Exception as e:
            print(f"❌ 요청 중 오류 발생: {e}")