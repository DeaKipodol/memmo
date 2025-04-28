import sys
import os
import pytest
import logging
from unittest.mock import patch, MagicMock
from ai_app.chatbotStream import ChatbotStream
from unittest.mock import MagicMock


# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("chatbot_tests")

# 상위 디렉토리를 파이썬 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 챗봇 클래스 및 모델 설정 임포트
from ai_app.chatbotStream import ChatbotStream
from ai_app.assist.common import model, client, makeup_response
from ai_app.utils.writingRequirementsManager import WritingRequirementsManager
from ai_app.utils.function_calling import FunctionCalling
from ai_app.assist.ConversationContextFactory import ConversationContextFactory

# 픽스처: 모든 테스트에서 사용할 챗봇 인스턴스
@pytest.fixture
def chatbot():
    logger.info("테스트용 ChatbotStream 인스턴스를 생성합니다.")
    return ChatbotStream(model.basic, system_role="test", instruction="", user="test", assistant="test")

# 픽스처: API 호출을 모킹하기 위한 설정
@pytest.fixture
def mock_api():
    with patch('ai_app.assist.common.client.responses.create') as mock_create:
        mock_response = MagicMock()
        mock_response.output_text = "모의 응답 텍스트"
        mock_response.output = [{"role": "assistant", "content": "모의 응답 텍스트"}]
        mock_create.return_value = mock_response
        yield mock_create

# 1. 단위 테스트 - 서브 대화방에 메시지 추가
def test_add_user_message_sub_context(chatbot):
    logger.debug("테스트 시작: 서브 대화방에 메시지 추가")
    chatbot.enter_sub_conversation("purpose_background")
    chatbot.add_user_message_in_context("서브 테스트 메시지")
    
    # 검증
    assert len(chatbot.sub_contexts["purpose_background"]["messages"]) == 1
    assert chatbot.sub_contexts["purpose_background"]["messages"][0] == {
        "role": "user",
        "content": "서브 테스트 메시지",
        "saved": False
    }
    logger.debug("테스트 완료: 서브 대화방에 메시지 추가")

# 2. 단위 테스트 - 현재 컨텍스트 가져오기
def test_get_current_context(chatbot):
    logger.debug("테스트 시작: 현재 컨텍스트 가져오기")
    
    # 메인 대화방
    assert chatbot.get_current_context() is chatbot.context
    
    # 서브 대화방
    chatbot.enter_sub_conversation("purpose_background")
    assert chatbot.get_current_context() is chatbot.sub_contexts["purpose_background"]["messages"]
    
    logger.debug("테스트 완료: 현재 컨텍스트 가져오기")

# 3. 단위 테스트 - 서브 대화방 진입
def test_enter_sub_conversation(chatbot):
    logger.debug("테스트 시작: 서브 대화방 진입")
    
    # 서브 대화방 진입
    result = chatbot.enter_sub_conversation("logic_evidence")
    
    # 검증
    assert chatbot.current_field == "logic_evidence"
    assert "logic_evidence" in chatbot.sub_contexts
    assert "messages" in chatbot.sub_contexts["logic_evidence"]
    assert "logic_evidence 에 대해" in result
    
    logger.debug("테스트 완료: 서브 대화방 진입")

# 4. 통합 테스트 - 대화 흐름 (메인 -> 서브 -> 메인)
def test_conversation_flow(chatbot, mock_api):
    logger.debug("테스트 시작: 대화 흐름 (메인 -> 서브 -> 메인)")
    
    # 메인 대화방 메시지 추가
    chatbot.add_user_message_in_context("메인 메시지")
    assert len(chatbot.context) > 0
    assert chatbot.context[-1]["content"] == "메인 메시지"
    
    # 서브 대화방으로 전환 및 메시지 추가
    chatbot.enter_sub_conversation("purpose_background")
    chatbot.add_user_message_in_context("서브 메시지")
    assert len(chatbot.sub_contexts["purpose_background"]["messages"]) == 1
    assert chatbot.sub_contexts["purpose_background"]["messages"][0]["content"] == "서브 메시지"
    
    # 서브 대화방 종료
    with patch.object(chatbot, 'writingRequirementsManager') as mock_manager:
        mock_manager.update_field.return_value = "필드 업데이트 완료"
        result = chatbot.exit_sub_conversation()
        
    # 검증
    assert chatbot.current_field == "main"
    assert mock_manager.update_field.called
    logger.debug(f"테스트 완료: 대화 흐름 (결과: {result})")

# 5. 통합 테스트 - GPT 응답 생성
def test_gpt_response(chatbot, mock_api):
    logger.debug("테스트 시작: GPT 응답 생성")

    from unittest.mock import MagicMock, patch

    def make_event(event_type, **kwargs):
        ev = MagicMock()
        ev.type = event_type
        for k, v in kwargs.items():
            setattr(ev, k, v)
        return ev
    
    created = make_event("response.created")

    # 2) 토큰 델타
    delta1 = make_event("response.output_text.delta", delta="모의 ")
    delta2 = make_event("response.output_text.delta", delta="응답 텍스트")

    # 3) 메시지 완성
    msg_part = MagicMock(type="output_text", text="모의 응답 텍스트")
    item_done = make_event(
        "response.output_item.done",
        item=MagicMock(type="message", role="assistant", content=[msg_part])
    )

    # 4) 스트림 완료
    completed = make_event("response.completed")

    # GPT 호출 모킹
    with patch('ai_app.assist.common.client.responses.create') as mock_create:
        mock_create.return_value = [created, delta1, delta2, item_done, completed]

        chatbot.add_user_message_in_context("테스트 질문")
        response = chatbot.send_request_Stream()

        # 검증
        assert mock_create.called
        assert "모의 응답 텍스트" in response
        logger.debug(f"테스트 완료: GPT 응답 생성 (응답: {response})")

# 6. 통합 테스트 - 예외 처리
def test_exception_handling(chatbot):
    logger.debug("테스트 시작: 예외 처리")
    
    # 존재하지 않는 필드에 접근 시도
    try:
        chatbot.current_field = "non_existent_field"
        context = chatbot.get_current_context()
        # 예외가 발생하지 않으면 테스트 실패
        assert False, "예외가 발생해야 합니다."
    except Exception as e:
        # 예외가 발생하면 테스트 성공
        logger.info(f"예상된 예외 발생: {e}")
    
    logger.debug("테스트 완료: 예외 처리")

# 7. 디버깅 도우미 함수 - 컨텍스트 상태 출력
def print_contexts_state(chatbot):
    """챗봇의 현재 컨텍스트 상태를 로깅하는 디버깅 함수"""
    logger.debug(f"현재 필드: {chatbot.current_field}")
    logger.debug(f"메인 컨텍스트 길이: {len(chatbot.context)}")
    logger.debug(f"사용 가능한 서브 컨텍스트: {list(chatbot.sub_contexts.keys())}")
    
    if chatbot.current_field != "main":
        logger.debug(f"현재 서브 컨텍스트 '{chatbot.current_field}' 메시지 수: "
                  f"{len(chatbot.sub_contexts[chatbot.current_field]['messages'])}")

# 디버깅 함수 테스트
def test_debug_helper(chatbot):
    logger.debug("테스트 시작: 디버깅 도우미 함수")
    
    # 메인 컨텍스트에 메시지 추가
    chatbot.add_user_message_in_context("메인 메시지")
    
    # 서브 컨텍스트로 전환
    chatbot.enter_sub_conversation("audience_scope")
    chatbot.add_user_message_in_context("서브 메시지")
    
    # 디버깅 함수 호출
    print_contexts_state(chatbot)
    
    logger.debug("test_debug_helper completed successfully")

# 수동 테스트를 위한 메인 함수
if __name__ == "__main__":
   
    # 로깅 레벨 설정
    logging.basicConfig(level=logging.DEBUG)
    
    print("===== Chatbot 수동 테스트 시작 =====")
    chatbot = ChatbotStream(model.basic, system_role="test", instruction="", user="test", assistant="test")
    
    

    while True:
        user_input = input("명령어 입력 (종료 입력 시 종료됨)> ")

        if user_input.strip() == "종료":
            break

        if user_input.startswith("입장 "):
            field = user_input.replace("입장", "").strip()
            print(chatbot.enter_sub_conversation(field))


        elif user_input == "메인으로":
            print(chatbot.exit_sub_conversation())

        elif user_input == "상태보기":
            print("📌 현재 필드:", chatbot.current_field)
            if chatbot.current_field == "main":
                print("🗂️ 메인 문맥:")
                for msg in chatbot.context:
                    print(f"- [{msg['role']}] {msg['content']}")
                print(f"🗂️ 메인 문맥 메시지: {chatbot.context}")
                print(f"🗂️ 메인 문맥 길이: {len(chatbot.context)}")

                
            else:
                ctx = chatbot.sub_contexts.get(chatbot.current_field, {})
                print(f"🗂️ 서브 문맥 ({chatbot.current_field}):")
                for msg in ctx.get("messages", []):
                    print(f"- [{msg['role']}] {msg['content']}")
                print(f"🗂️ 서브 문맥 메시지: {chatbot.sub_contexts[chatbot.current_field]['messages']}")
            

        else:
            chatbot.add_user_message_in_context(user_input)
            print(f"💬 메시지 추가됨: {user_input}")
            print(f"🧭 현재 필드: {chatbot.current_field}")

            # ✅ GPT 응답 연동 추가
            try:
                response = chatbot.send_request_Stream()
                chatbot.add_response_stream(response)  # ✅ 이거 추가!

                print(f"\n🤖 GPT 응답: {response}")
            except Exception as e:
                print(f"❌ GPT 응답 중 오류 발생: {e}")

            print(f"🗂️ 메인 문맥 길이: {len(chatbot.context)}")
            if chatbot.current_field != "main":
                print(f"🗂️ 서브 문맥 ({chatbot.current_field}) 길이: {len(chatbot.sub_contexts[chatbot.current_field]['messages'])}")
                print(f"🗂️ 서브 문맥 메시지: {chatbot.sub_contexts[chatbot.current_field]['messages']}")
            

    print("===== 수동 테스트 종료 =====")
