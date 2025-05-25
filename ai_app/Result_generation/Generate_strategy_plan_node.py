import logging
from typing import Dict, List, Any
from pydantic import ValidationError
from data.data_models import AgentState, CoTStrategyPlan, WritingRequirements
import json
from data.validators import autofill_missing_fields, validate_section_plan_fields


from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from ai_app.assist.common import model as common_model
from ai_app.assist.common import api_key 
from ai_app.assist.common import client, model



logger = logging.getLogger(__name__)

def generate_strategy_plan_node(state: AgentState) -> AgentState:
    """
        Generate a strategy plan using LangChain's responses API integration.
        
        This function uses the ChatOpenAI model (with the responses API JSON output mode) 
        to generate a strategy plan that adheres to the CoTStrategyPlan schema. 
        It constructs a prompt from the writing requirements, invokes the LLM with 
        structured JSON output formatting, and parses the result into a CoTStrategyPlan object.
        The OpenAI API key is utilized via the common client for authentication.
        Returns the updated AgentState with the generated CoTStrategyPlan or an error message.
    """
    logger.info("--- 🧠 CoT_StrategyGeneratorNode 실행 시작 (Responses API) ---")
    try:
        # 1. 요구사항 준비
        requirements: WritingRequirements = autofill_missing_fields(state.requirements)
        state.requirements = requirements
        
        requirements_dict = requirements.model_dump(exclude_none=True)
        logger.debug("요구사항 데이터:\n%s", json.dumps(requirements_dict, indent=2))

        # 2. LLM 초기화 (Responses API + JSON 모드)
        llm = ChatOpenAI(
            model_name=common_model.advanced,
            temperature=None,
            openai_api_key=api_key,
            use_responses_api=True,
            model_kwargs={"response_format": {"type": "json_object"}}
        )

        # 3. 출력 파서 (Pydantic → CoTStrategyPlan)
        output_parser = PydanticOutputParser(pydantic_object=CoTStrategyPlan)

        # 4. 프롬프트 구성
        system_message = """
        당신은 대규모 언어 모델을 활용해 복잡한 사용자 요구사항을 해석하고, 글쓰기의 구조, 흐름, 문체, 제약 조건을 모두 반영한 실행 가능한 전략
           계획을 JSON 형식으로 생성하는 전략 전문가입니다.당신의 출력은 반드시 CoTStrategyPlan JSON 스키마를 충실히 따르며, 다음 조건을 반드시 만족해야 합니다:
        1. writing_type, core_message, target_audience_insight, tone_and_manner, constraints_to_observe, section_plan의 모든 필드를 반드시 포함하십시오. 어떤 항목도 누락되어서는 안 됩니다.

        2. section_plan 필드에는 하나 이상의 섹션이 포함되어야 하며, 각 섹션에는 반드시 다음 항목을 포함해야 합니다:
           - section_name: 이 섹션의 이름 (예: introduction, body_experience, conclusion 등)
           - purpose_or_goal: 이 섹션이 독자에게 전달해야 할 핵심 목적 또는 메시지
           - relevant_requirements_fields: 해당 섹션 작성 시 참조할 사용자 요구사항 필드명 리스트 (총 8개 필드 중 하나 이상 포함)
           - writing_guideline_or_flow: 이 섹션을 어떤 흐름과 방식으로 구성해야 하는지 구체적인 작성 지침

         3.`section_plan`에 있는 모든 섹션의 `relevant_requirements_fields` 리스트들을 전부 합쳤을 때,
           다음 8개의 요구사항 필드명(`purpose_background`, `context_topic`, `audience_scope`, `format_structure`, `logic_evidence`, `expression_method`, `additional_constraints`, `output_expectations`)이
           단 하나도 빠짐없이 **모두** 포함되어야 합니다. 각 필드는 최소 한 번 이상 사용되어야 합니다. 누락되는 필드가 없도록 각별히 주의하십시오.**

        4. 출력은 오직 순수한 JSON 객체만 포함되어야 하며, 마크다운, 주석, 해설 문장 등은 절대 포함하지 마십시오.
        5. 한국말로 작성하세요.


        """

        human_template = """다음은 사용자의 글쓰기 요구사항입니다:
                ```json
                    {requirements_input}
                ```

                다음 JSON 스키마를 반드시 따라 출력하세요:
                    {format_instructions}

                JSON 외의 설명 없이, 순수한 JSON만 출력해주세요.
                    한국말로 작성하세요.

                """

        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_message),
            HumanMessagePromptTemplate.from_template(human_template)
        ])

        # 5. LangChain 체인 실행
        chain = prompt | llm | output_parser
        parsed_strategy_plan = chain.invoke({
            "requirements_input": json.dumps(requirements_dict, indent=2),
            "format_instructions": output_parser.get_format_instructions()
        })
        logger.debug("GPT로부터 받은 전략:\n%s", parsed_strategy_plan.model_dump_json(indent=2))

     
        
        validate_section_plan_fields(parsed_strategy_plan)
        state.generated_strategy_plan = parsed_strategy_plan


        logger.info("✅ 모든 요구사항 필드가 section_plan에 반영됨.")
        state.current_operation_step = "전략 계획 생성 완료 (Responses API)"
        logger.info("✅ CoT 전략 생성 완료: %s", parsed_strategy_plan.writing_type)

    except ValidationError as ve:
        logger.error("❌ Pydantic 검증 실패", exc_info=ve)
        state.error_message = f"전략 검증 실패: {str(ve)}"
        state.generated_strategy_plan = None

    except Exception as e:
        logger.exception("❌ 전략 생성 중 예외 발생")
        error_message_detail = str(e)
        if hasattr(e, 'llm_output'):
            error_message_detail += f"\nLLM Raw Output: {e.llm_output}"
        state.error_message = f"전략 생성 오류: {error_message_detail}"
        state.generated_strategy_plan = None

    logger.info("--- 🧠 CoT_StrategyGeneratorNode 실행 종료 ---")
    # ─── 디버깅: 최종 반환 타입 확인 ───
    logger.debug(f"[STRATEGIST] 반환 타입: {type(state)} / 값: {state!r}")
    return state
