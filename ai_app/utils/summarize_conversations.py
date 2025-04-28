from ai_app.assist.common import client,model
import json
from retry import retry
from ai_app.assist.characters import system_role_summerizeJson
system_role =system_role_summerizeJson
with open("테스트용대화원본.json", "r", encoding="utf-8") as f:
    conversations = json.load(f)#테스트용대화원본.json파일을 읽어서 conversations에 저장
summaries = []

@retry(tries=5, delay=2)
def summarize_conversation(conversation):
    try:
        #요약을 위한 원본 대화 json을 dumps를 이용하여 문자열로 변환
        #dumps는 json형식을 문자열로 변환(loads는 문자열을 json형식으로 변환)
        conversation_str = json.dumps(conversation, ensure_ascii=False)
        message = [{"role": "user", "content": system_role}, {"role": "assistant", "content": conversation_str}]
        response=client.responses.create(
            model=model.advanced,
            input=message,
            response_format={"type": "json_object"}
        ).model_dump()
        content=response['choices'][0]['message']['content']
        print(content)
        #원본을 요약함.

        #요약본을 json으로 변환
        summary=json.loads(content)
        #summeries에 요약내용을 data에서 가져와 추가
        summaries.append(summary["data"])
    except Exception as e:
        print(f"예외 발생: {e}")
        raise e
for conversation in conversations:
    summarize_conversation(conversation)

#요약된 대화를 JSON 파일로 저장
with open("요약된대화.json", "w", encoding="utf-8") as f:
    json.dump(summaries, f, ensure_ascii=False, indent=4)
        