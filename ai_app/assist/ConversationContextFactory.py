from typing import TypedDict, Literal, List

class MessageDict(TypedDict):
    role: Literal["user", "assistant"]
    content: str

class ContextDict(TypedDict):
    field_name: str
    messages: List[MessageDict]        # ✔ 메시지 구조까지 고정
    summary: str
    clarification_question: str

class ConversationContextFactory:
    @staticmethod
    def create_context(field_name: str) -> ContextDict:
        """
        주어진 field_name에 대한 대화 문맥 객체를 생성합니다.
        
        Args:
            field_name (str): 대화의 주제나 필드 이름.
        
        Returns:
            dict: 대화 문맥 객체.
        """
        return {
            "field_name": field_name,
            "messages": [],  # 대화 내용 저장
            "summary": "",  # 대화 요약
            "clarification_question": ""  # 사용자에게 물어볼 질문
        }
    '''사용예시
    context = ConversationContextFactory.create_context("purpose_background")
    print(context)
# 출력: {'field_name': 'purpose_background', 'messages': [], 'summary': '', 'clarification_question': ''}'''