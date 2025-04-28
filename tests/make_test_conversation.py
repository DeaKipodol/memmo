from ai_app.assist.common import client,model
import json
from ai_app.assist.characters import system_role
prompt='''
-당신은 사용자와 글쓰기 도움이인 챗봇 사이의 대화데이터를 만듭니다.
-Each conversation dataset should involve different writing formats (e.g., journal, article, poem, letter) and explore a variety of topics to ensure richness and versatility.
-샘플형식은 아래와 같은 json 타입입니다.
,,,
{
    "data":[
            {"user":"안녕?"},
            {"assistant":"안녕하세요! 저는 여러분의 글쓰기 프로젝트를 명확히 하고 개발하는 데 도움을 주는 대화형 조수입니다. 여러분이 글쓰기에 대해 어떤 생각을 가지고 계신지, 혹은 어떤 도움이 필요 한지 말씀해주시면 함께 진행해보겠습니다."},
            {"user":"나는 일기를 적을거야"},
            {"assistant":"기 쓰기는 정말 좋은 생각입니다. 일기는 개인적인 생각과 경험을 표현하는 데 도움이 되며, 자기 성찰과 기억 보존에 유용할 수 있습니다. 일기의 목적이나 기능에 대해 좀 더 구체적으로 생각해보셨나요? 예를 들어, 감정을 표현하는 것에 중점을 두실 건지, 아니면 매일 일어나는 사건들을 기록하는 데 더 중점을 두실 건지 말입니다."},
            {"user":"글쎄 매일 매일 적기 귀찮지만 하루의 일상을 정리할 필요가 있어서, 하루하루 소중한데 잊어버리는게 너무 아까워서 일기를 적으려고"},
            {"assistant":"하루하루의 소중한 순간들을 기록하고 싶은 욕구와 함께 일기 쓰기가 때로는 번거로울 수 있다는 점을 이해합니다. 이런 경우, 일기 쓰기를 덜 부담스럽게 만드는 몇 가지 방법을 고려해볼 수 있습니다:"},
             {"user":"그냥 하루생긴일 주저리주저리 말할거야"},
            {"assistant":"하루에 생긴 일들을 주저리주저리 말씀하고 싶으시다면, 일기 형식이 아주 적합해 보입니다. 이러한 접근 방식은 생각이나 감정을 자유롭게 표현하는 데 도움을 줄 수 있으며, 형식에 구애받지 않고 자신의 경험을 솔직하게 기록하는 데 이상적입니다. 그렇다면, 이 일기를 통해 어떤 감정이나 생각들을 특별히 표현하고 싶으신가요, 아니면 단순히 일상의 사건들을 기록하는 데 초점을 두고 싶으신가요?"}

            ]
}
,,,

- Create a single conversation dataset that includes a total of 30 dialogue turns (combined count of user and assistant messages).  
- Ensure that the writing topic and format vary naturally throughout the dialogue.  
- Each turn should follow the logical flow of a real conversation between the user and a writing assistant.  
,,,

챗봇에게 부여된 역할은 다음과 같습니다:
system_role='You are a conversational assistant designed to help users clarify and develop their writing projects by uncovering hidden or unclear topics through conversation.
Your task is to guide users by identifying key elements of their writing goals and deducing topics that are not immediately apparent in the user's statements.
You should always contextualize within the conversation like a socially adept detective, similar to Sherlock Holmes.'

 한국어로 말해주세요.'



 '''

conversations = []
context = [{"role": "system", "content": system_role},
           {"role": "user", "content": prompt}]
successful_runs = 0
while successful_runs < 5:#5일치 만들것, 30개씩 5세트
    try:
        response = client.chat.completions.create(
                    model="gpt-4o", 
                    messages=context,
                    temperature=1,
                    response_format={"type": "json_object"}
                ).model_dump()
        content = response['choices'][0]['message']['content']
        print(content)
        #GPT가 만든 JSON 응답에서 "data" 항목만 꺼내서 저장
        conversation = json.loads(content)["data"]
        print(f"{successful_runs}번째 종료\n")

        # 만들어진 대화 데이터를 전체 리스트에 추가
        conversations.append(conversation)
        successful_runs += 1
    except Exception as e:
        print("예외 발생, 재시도합니다.", e)
# conversations 리스트를 JSON 파일로 저장
with open('테스트용대화원본.json', 'w', encoding='utf-8') as f:
    json.dump(conversations, f, ensure_ascii=False, indent=4)

'''"
1.대화원천내용.json"이라는 파일을 **쓰기 모드('w')**로 열고,

인코딩은 UTF-8로 설정해서 한글이 깨지지 않도록 해줌.

with 구문을 쓰면 파일을 다 쓰고 나서 자동으로 파일을 닫아줘서 편리하고 안전

2. json.dump(conversations, f, ensure_ascii=False, indent=4)
conversations 리스트를 f (파일 객체)에 JSON 형식으로 저장.

ensure_ascii=False → 한글을 유니코드가 아니라 원래 문자 그대로 저장해 줌.

indent=4 → 보기 좋게 들여쓰기 4칸으로 정렬해서 저장함 (예쁘게 저장되는 옵션).
'''