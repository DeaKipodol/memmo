import json
from ai_app.assist.common import client, model,makeup_response
from ai_app.assist.characters import get_update_field_prompt  # 추가된 부분
class WritingRequirementsManager:
    def __init__(self):
        '''"purpose_background": 목적 및 배경
        "context_topic": 맥락 및 주제
        "audience_scope": 독자 및 범위
        "format_structure": 형식 및 구조
        "logic_evidence": 논리 전개 및 증거
        "expression_method": 표현 방식
        "additional_constraints": 추가 자료 및 제약 사항
        "output_expectations": 결과물 기대치'''
        self.writing_requirements = {
            "purpose_background": None,
            "context_topic": None,
            "audience_scope": None,
            "format_structure": None,
            "logic_evidence": None,
            "expression_method": None,
            "additional_constraints": None,
            "output_expectations": None,
        }
        

    def update_field(self, field_name, new_content):
        """
        특정 필드의 값을 새로운 값으로 업데이트.

        Args:
            field_name (str): 업데이트할 필드 이름 (writing_requirements 딕셔너리의 키)
            new_content (any): 필드에 저장할 새로운 값
        """
        
        if field_name in self.writing_requirements:
             # 1. 이전 내용 가져오기
            previous_content = self.writing_requirements[field_name]
             # 2. 새로운 요구사항과 이전 내용을 텍스트로 연결 (이전 내용이 None일 경우 처리)
            if previous_content:
                combined_content = str(previous_content) + "\n" + str(new_content)
            else:
                combined_content = str(new_content) # 이전 내용이 None이면 새 값만 사용
            try:
                field_prompt = get_update_field_prompt(field_name, combined_content)
                response = client.responses.create(
                    model=model.advanced, 
                    input=[field_prompt],
                )
                summarized_content = response.output_text # 요약된 내용 추출
                self.writing_requirements[field_name] = summarized_content
                print(f"DEBUG:필드 '{field_name}' 업데이트 및 요약 완료:")
                print(self.get_field_content(field_name))
                return f"사용자가 요청한 업데이트 필드 '{field_name}' 업데이트 및 요약 완료를 알려라. 1문장 짧게..이후 관련 되어 궁금하거나 도움이될수있는 질문을 던져라"

            except Exception as e: # GPT API 호출 실패 시 예외 처리
                print(f"DEBUG: \n GPT API 요약 오류 발생 (필드 '{field_name}' 업데이트): {e}")
                self.writing_requirements[field_name] = new_content # 요약 실패 시 새 값으로만 업데이트 (fallback)
                print(f"DEBUG: \n필드 '{field_name}' 새 내용으로 업데이트 (요약 생략):")
                print(self.get_field_content(field_name))
                return "사용자가 요청한  GPT API 요약 오류 발생을 알려라 1문장 짧게.이후 관련 되어 궁금하거나 도움이될수있는 질문을 던져라.(필드 '{field_name}' 업데이트): {e}"

        elif not field_name or not new_content:
              print(f"오류: 필드 '{field_name}'가 존재하지 않습니다.")
              return f"오류: 필드 '{field_name}'가 존재하지 않음을 알려라.memmoCopany@000-0000에게 건의하라고 알려라.."
    def get_requirements(self):
        """
        현재 writing_requirements 딕셔너리를 반환합니다.

        Returns:
            dict: writing_requirements 딕셔너리
        """
        return self.writing_requirements
    def get_field_content(self,field_name=None):
        """
        필드 내용을 확인하는 함수.

        Args:
            field_name (str, optional): 확인할 특정 필드 이름 (None이면 작성된 모든 필드 내용 출력). Defaults to None.

        Returns:
            str: 필드 내용 (field_name이 지정된 경우) 또는 작성된 필드 목록 및 내용 (field_name이 None인 경우).
                 필드 내용이 없으면 "작성된 내용이 없습니다." 메시지 반환.
        """
        if field_name: # 1. 특정 필드에 대한 내용 출력 요청
            if field_name in self.writing_requirements:
                content = self.writing_requirements[field_name]
                if content: # 필드에 내용이 있는 경우
                    print(f"'{field_name}' 필드 내용:\n{content}")      
                    return f"'{field_name}' 필드 내용:\n{content}" 
                    
            else: # 존재하지 않는 필드 이름
                print(f"오류: 필드 '{field_name}'는 존재하지 않습니다.")
                return f"오류: 필드 '{field_name}'는 존재하지 않습니다.사용자에게 찾아봤으나 현재 요청한 내용을 지원못한다고 알리세요 "

        else: # 2. 작성된 필드에 대한 내용 출력 요청 (field_name is None)
            written_fields = []
            for name, content in self.writing_requirements.items():
                if content: # 필드에 내용이 있는 경우
                    written_fields.append(f"{name}: {content}")

            if written_fields: # 작성된 필드가 있는 경우
                print("현재 작성된 글쓰기 요구사항 필드:\n" + "\n".join(written_fields))
                return "현재 작성된 글쓰기 요구사항 필드:\n" + "\n".join(written_fields)
            else: # 작성된 필드가 없는 경우
                print("작성된 글쓰기 요구사항이 아직 없습니다.")
                return "작성된 글쓰기 요구사항이 아직 없습니다. 이야기를 조금 더 나누어야 된다고 알리세요 "
    
    def reset_requirements(self):
        """
        writing_requirements 딕셔너리의 모든 필드를 초기화합니다.
        """
        for field in self.writing_requirements:
            self.writing_requirements[field] = None
    #writing_requirements 에 값을 업데이트하는 과정
    #사용자 입력->functioncall
    # -> WritingREquirement에 updatefield를 실행: 매개변수:값:=> 이후 실행로직 

        