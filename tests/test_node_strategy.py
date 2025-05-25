import os
import sys

# 프로젝트 루트 디렉토리를 시스템 경로에 추가
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
# 1. 테스트 대상 함수 임포트
from ai_app.Result_generation.nodes import generate_strategy_plan_node # 고객님의 nodes.py 에서 함수 임포트
# 2. Pydantic 모델 임포트
from data.data_models import AgentState, WritingRequirements, CoTStrategyPlan
# 3. 테스트 데이터 임포트
from data.sampleRequirements import test_data_set_A , test_data_set_B, test_data_set_C # 또는 다른 테스트 세트
import logging

# 로깅 기본 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_node_test():
    logger.info("===== 🧪 generate_strategy_plan_node 테스트 시작 =====")
    
    try:
        requirements_instance = WritingRequirements.model_validate(test_data_set_A)
        
    except Exception as e:
        logger.error("WritingRequirements Pydantic 모델 변환 실패: %s", e)
        return

    initial_state = AgentState(requirements=requirements_instance)
    
    logger.info("초기 AgentState.requirements:\n%s", initial_state.requirements.model_dump_json(indent=2))
    
    updated_state = generate_strategy_plan_node(initial_state)
    
    if updated_state.error_message:
        logger.error("테스트 중 오류 발생: %s", updated_state.error_message)
    elif updated_state.generated_strategy_plan:
        plan = updated_state.generated_strategy_plan
        logger.info("생성된 전략 계획 상세 내용:")
        logger.info("  글쓰기 유형 (writing_type): %s", plan.writing_type)
        logger.info("  핵심 메시지 (core_message): %s", plan.core_message)
        logger.info("  독자 분석 (target_audience_insight): %s", plan.target_audience_insight) # ✅ 추가된 확인
        logger.info("  톤앤매너 (tone_and_manner): %s", plan.tone_and_manner) # ✅ 추가된 확인
        
        if plan.constraints_to_observe: # ✅ 추가된 확인 (리스트이므로 내용도 함께 로깅)
            logger.info("  준수 제약 조건 (constraints_to_observe):")
            for constraint in plan.constraints_to_observe:
                logger.info("    - %s", constraint)
        else:
            logger.info("  준수 제약 조건 (constraints_to_observe): 없음")

        if plan.section_plan:
            logger.info("  섹션 계획 (section_plan) 수: %d", len(plan.section_plan))
            for i, section in enumerate(plan.section_plan):
                logger.info("    --- 섹션 %d: %s ---", i + 1, section['section_name'])
                logger.info("      목표 (purpose_or_goal): %s", section['purpose_or_goal'])
                logger.info("      관련 요구사항 필드 (relevant_requirements_fields): %s", section['relevant_requirements_fields'])
                logger.info("      작성 가이드라인 (writing_guideline_or_flow): %s", section['writing_guideline_or_flow'])
            
                required_keys = {"section_name", "purpose_or_goal", "relevant_requirements_fields", "writing_guideline_or_flow"}
                missing = required_keys - section.keys()
                assert not missing, f"❌ 섹션 {i + 1}에 누락된 필드 있음: {missing}"
                
        else:
            logger.warning("  섹션 계획 (section_plan)이 생성되지 않았습니다.")
            assert False, "❌ section_plan이 생성되지 않음"
        from data.validators import validate_section_plan_fields
        validate_section_plan_fields(plan)

        # 전체 JSON 출력은 그대로 유지 (상세 검토용)
        logger.info("전체 전략 계획 (JSON):\n%s", plan.model_dump_json(indent=2, exclude_none=True))
        logger.info("테스트 성공! ✅")
    else:
        logger.warning("오류 메시지는 없으나, 전략 계획이 생성되지 않았습니다. (updated_state.generated_strategy_plan is None)")
        
    logger.info("===== 🧪 generate_strategy_plan_node 테스트 종료 =====")

if __name__ == "__main__":
    # 로깅 기본 설정 (테스트 스크립트 실행 시 로그를 보기 위함)
    logging.basicConfig(
        level=logging.DEBUG, # DEBUG 레벨 이상 모두 출력 (nodes.py의 DEBUG 로그도 보려면)
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler() # 콘솔 출력 핸들러
        ]
    )
    run_node_test()