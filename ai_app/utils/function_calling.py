from ai_app.assist.common import client, model, makeup_response
import json
import requests
from pprint import pprint
from tavily import TavilyClient
import os
from ai_app.utils.writingRequirementsManager import WritingRequirementsManager


tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
global_lat_lon = { 
           '서울':[37.57,126.98],'강원도':[37.86,128.31],'경기도':[37.44,127.55],
           '경상남도':[35.44,128.24],'경상북도':[36.63,128.96],'광주':[35.16,126.85],
           '대구':[35.87,128.60],'대전':[36.35,127.38],'부산':[35.18,129.08],
           '세종시':[36.48,127.29],'울산':[35.54,129.31],'전라남도':[34.90,126.96],
           '전라북도':[35.69,127.24],'제주도':[33.43,126.58],'충청남도':[36.62,126.85],
           '충청북도':[36.79,127.66],'인천':[37.46,126.71],
           'Boston':[42.36, -71.05],
           '도쿄':[35.68, 139.69]
          }
global_currency_code = {'달러':'USD','엔화':'JPY','유로화':'EUR','위안화':'CNY','파운드':'GBP'}

def get_celsius_temperature(**kwargs):
    location = kwargs['location']
    lat_lon = global_lat_lon.get(location, None)
    if lat_lon is None:
        return None
    lat = lat_lon[0]
    lon = lat_lon[1]

    # API endpoint
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"

    # API를 호출하여 데이터 가져오기
    response = requests.get(url)
    # 응답을 JSON 형태로 변환
    data = response.json()
    # 현재 온도 가져오기 (섭씨)
    temperature = data['current_weather']['temperature']

    print("temperature:",temperature) 
    return temperature

def get_currency(**kwargs):    

    currency_name = kwargs['currency_name']
    currency_name = currency_name.replace("환율", "")
    currency_code = global_currency_code.get(currency_name, 'USD')
    
    if currency_code is None:
        return None

    response = requests.get(f"https://api.exchangerate-api.com/v4/latest/{currency_code}")
    data = response.json()
    krw = data['rates']['KRW']

    print("환율:", krw) 
    return krw

def search_internet(user_input: str,chat_context=None) -> str:
    
    try:
        print(f"📨 웹 검색 요청 시작: '{user_input}'")

        # ✅ 사용자 입력을 input_text 컨텍스트로 변환
       
        if chat_context:
            print("🔄 문맥 처리 시작")
        # 최근 N개의 메시지만 포함 (너무 많은 문맥은 토큰을 낭비할 수 있음)
            recent_messages = chat_context[-3:]  # 최근 3개 메시지만 사용
            print(f"📋 최근 메시지 수: {len(recent_messages)}")
            # 문맥 정보를 추가 컨텍스트로 구성
            for i, msg in enumerate(recent_messages):
                    print(f"📝 메시지 {i + 1} 역할: {msg.get('role', 'unknown')}")
                    content_preview = str(msg.get('content', ''))[:50] + "..." if len(str(msg.get('content', ''))) > 50 else str(msg.get('content', ''))
                    print(f"📄 내용 미리보기: {content_preview}")

            context_info = "\n".join([
                f"{msg.get('role', 'unknown')}: {msg.get('content', '')}" 
                for msg in recent_messages if msg.get('role') != 'system'
            ])
            
            
            search_text = client.responses.create(
                model="gpt-4o",
                input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"{user_input}\n\n[대화 문맥]: {context_info} 을 제공된 문맥에 맞게 검색어를 새로 만들어라 <예)/>  문맥: 창업가양성교육...; 사용자 요청:25년 정보로 검색해줘; 검색어[창업양성교육 25년]검색어는 단어의 조합이어야된다.</예예>"
                        }
                    ]
                }
            ],
        ).output_text
            print("문맥DEBUG!!!!!!!!!!!!!!!!!!")
            print(search_text)
            print("\n\n\n\n")
        else:
            search_text = user_input 
            print("없는 문맥DEBUG!!!!!!!!!!!!!!!!!!")
            print(search_text)
            print("\n\n\n\n")
        context_input = [
        {
            "role": "user",
            "content": [{"type": "input_text", "text": search_text}]
        }
    ]

        response = client.responses.create(
            model="gpt-4o",
            input=context_input,  
            text={"format": {"type": "text"}},
            reasoning={},
            tools=[{
                "type": "web_search_preview",
                "user_location": {
                    "type": "approximate",
                    "country": "KR"
                },
                "search_context_size": "medium"
            }],
            tool_choice={"type": "web_search_preview"},
            temperature=1,
            max_output_tokens=2048,
            top_p=1,
            store=True
        )
        
        # ✅ 웹 검색 수행 여부 로그
        if any(getattr(item, "type", None) == "web_search_call" for item in getattr(response, "output", [])):
            print("✅ 🔍 웹 검색이 실제로 수행되었습니다.")
        else:
            print("⚠️ 웹 검색이 수행되지 않았습니다.")

        # ✅ 응답 메시지 추출
        print("DEBUG: Extracting message object from response.output")

        # 1. message 객체 추출 (ResponseOutputMessage)
        message = next(
            (item for item in response.output if getattr(item, "type", None) == "message"),
            None
        )
        if not message:
            print("DEBUG: No message found")
            return "❌ GPT 응답 메시지를 찾을 수 없습니다."

        # 2. content 중 output_text 블록 추출
        print("DEBUG: Looking for output_text block in message.content")
        content_block = next(
            (block for block in message.content if getattr(block, "type", None) == "output_text"),
            None
        )
        if not content_block:
            print("DEBUG: output_text block not found")
            return "❌ GPT 응답 내 output_text 항목을 찾을 수 없습니다."

        # 3. 텍스트 추출
        output_text = getattr(content_block, "text", "").strip()
        print(f"DEBUG: Extracted output_text: {output_text}")

        # 4. 출처(annotation) 파싱
        annotations = getattr(content_block, "annotations", [])
        print(f"DEBUG: Annotations: {annotations}")
        citations = []
        for a in annotations:
            if getattr(a, "type", None) == "url_citation":
                print(f"DEBUG: Found url_citation: {a}")
            title = getattr(a, "title", "출처")
            url = getattr(a, "url", "")
            citations.append(f"[{title}]({url})")

        # 5. 텍스트 + 출처 조합
        result = output_text
        print(f"DEBUG: Collected citations: {citations}")
        if citations:
            result += "\n\n📎 출처:\n" + "\n".join(citations)
        
        return result+"이 응답 형식 그대로 출력하세요 대답과 출처가 형식 그대로 다음대답에 담겨야합니다.엄밀하게."

    

    except Exception as e:
        return f"🚨 파싱 중 오류 발생: {str(e)}"


    except Exception as e:
        return f"🚨 오류 발생: {str(e)}"


def search_internet_for_report(**kwargs):
    #print("search_internet",kwargs)
    response =tavily.search(query=kwargs['search_query'], max_results=2, search_depth="advanced")
    contents=[{"content":result['content'],"url":result['url']}
              for result in response['results']]
    #print("contents",contents)
    return f"수집된 자료:{contents}"
report_system_role = """
다음 내용을 바탕으로 보고서를 한국어로 작성해주세요. 보고서 작성 후 마지막에 검색에 활용한 url을 각주로 반드시 표시하세요.
"""
def write_report(**kwargs):   
    print('write_report',kwargs)
    response = client.chat.completions.create(
                    timeout=90,
                    model="gpt-4-1106-preview",  
                    messages=[
                        {"role": "system", "content": report_system_role},
                        {"role": "user", "content": kwargs['materials']}
                    ],
                )
    report = response.model_dump()['choices'][0]['message']['content']
    return report
tools = [
        {
            "type": "function",
            "name": "get_celsius_temperature",
            "description": "지정된 위치의 현재 섭씨 날씨 확인",
            "strict": True,
            "parameters": {
                "type": "object",
                "required": [
                    "location"
                ],
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "광역시도, e.g. 서울, 경기"
                    }
                },
                "additionalProperties": False
            }
},
       {
           "type": "function",
            "name": "get_currency",
            "description": "지정된 통화의 원(KRW) 기준의 환율 확인.",
            "strict": True,
            "parameters": {
                "type": "object",
                "required": [
                    "currency_name"
                ],
                "properties": {
                    "currency_name": {
                        "type": "string",
                        "description": "통화명, e.g. 달러환율, 엔화환율"
                    }
                },
                "additionalProperties": False
            }
            },
            {
            "type": "function",
            "name": "search_internet",
            "description": "Searches the internet based on user input and retrieves relevant information.",
            "strict": True,
            "parameters": {
                "type": "object",
                "required": [
                "user_input"
                ],
                "properties": {
                "user_input": {
                    "type": "string",
                    "description": "User's search query input(conversation context will be automatically added)"
                }
                },
                "additionalProperties": False
            }
            },
        {
  "type": "function",
  "name": "update_field",
  "description": """
시스템이 사용자가 작성 요구사항 내의 특정 필드를 업데이트하려는 의도를 감지하면 다음 단계를 따르세요:

1. 입력에서 ‘새로운 정보(new_content)’를 추출합니다.(1. new_content 정제  
   1.1. 문장 부호(. , “ ” ‘ ’ 등) 제거  
   1.2. 불필요 조사·접속사(는/은/이/가, 그리고/하지만 등) 간략히 필터링  
   1.3. 특수문자(# $ % & * 등) 트리밍 )

2. 아래의 기준에 따라 ‘field_name’을 결정합니다:
   • purpose_background  
     –사용자가 ‘이유’, ‘목적’, ‘배경’을 언급할 때  
     – 예: “나는 일기를 쓰려 해요”, “이 프로젝트의 목적은…”  
   • context_topic  
     – 글의 ‘주제’, ‘이야기거리’, ‘사례’ 등을 지칭할 때  
     – 예: “주제는 환경보호입니다”, “사례로 코로나 이후…”  
   • audience_scope  
     – ‘대상’, ‘독자’, ‘누구에게’ 같은 단어가 있을 때  
     – 예: “독자는 학생들입니다”, “대상은 초보개발자”  
   • format_structure  
     – ‘형식’, ‘구조’, ‘목차’, ‘파트’ 등을 지정할 때  
     – 예: “포맷은 보고서 형태로”, “1. 서론, 2. 본론…”  
   • logic_evidence  
     – ‘논리적 흐름’, ‘근거’, ‘데이터’, ‘사례’ 등을 언급 할때때 
     – 예: “우리가 전에 검색한 내용 있잖아..”, “조금 더 논리적으로 했으면 좋겠어어”  
   • expression_method  
     – ‘어조’, ‘스타일’, ‘톤’, ‘문체’ 언급 시  
     – 예: “친근한 어조로”, “격식 있는 문체로”  
   • additional_constraints  
     – ‘제한’, ‘금지’, ‘분량’, ‘키워드’ 같은 부가조건 언급 시  
     – 예: “500자 이내로”, “‘AI’라는 단어는 빼고” ,"이다 말고 음슴 식의 개조체로.."
   • output_expectations  
     – 최종 산출물 형태나 품질 기준 언급 시  
     – 예: “슬라이드로 만들어줘”, “요약문 형태로” ,"회사의 양식을 줄게 그거에 따라서 적어줘줘"

3. 추출된 ‘field_name’과 ‘new_content’를 파라미터로 호출합니다.

예시:
입력: “청중은 대학원생입니다.”
→ field_name: “audience_scope”
   new_content: “대학원생”
4.new_content는 현재 재화맥락 전체를 고려해라  (예) 만약 이전에 사용자가 검색을 한 문맥이 있는데 사용자가 근거를 업데이트해 하면 이전에 검색한 내용을 기반으로 newcontent를 만들어라- 단 최근 3개 대화만을 고려. 
""",
  "strict": True,
  "parameters": {
    "type": "object",
    "required": [
      "field_name",
      "new_content"
    ],
    "properties": {
      "field_name": {
        "type": "string",
        "description": "업데이트할 필드 이름 (writing_requirements 딕셔너리의 키)",
        "enum": [
          "purpose_background",
          "context_topic",
          "audience_scope",
          "format_structure",
          "logic_evidence",
          "expression_method",
          "additional_constraints",
          "output_expectations"
        ]
      },
      "new_content": {
        "type": "string",
        "description": "필드에 저장할 새로운 값"
      }
    },
    "additionalProperties": False
  }
},
       {
            "type":"function",
            
                "name": "get_writing_requirement_field_content",
                "description": """사용자가 작성 요구 사항 필드의 내용을 보길 원하면, 사용자가 보고 싶어하는 필드를 확인하세요 (하나 또는 여러 필드를 선택할 수 있습니다. 표시할 필드가 없으면 모든 필드를 표시하기로 결정하세요). 현재 작성된 작성 요구 사항 필드의 내용을 보여주세요..""",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "required": [
                    "field_name"
                    ],
                    "properties": {

                    "field_name": {
                        "type": "string",
                        "description": "확인할 특정 필드 이름 (선택 사항). 생략하면 작성된 모든 필드 내용을 반환합니다.",
                        "enum": [
                        "purpose_background",
                        "context_topic",
                        "audience_scope",
                        "format_structure",
                        "logic_evidence",
                        "expression_method",
                        "additional_constraints",
                        "output_expectations"
                        ]
                    }
                    },
                "additionalProperties": False
                
                }



            }
      
    ]


class FunctionCalling:
    def __init__(self, model):
        self.writingRequirementsManager=WritingRequirementsManager()
        self.available_functions = {
            "get_celsius_temperature": get_celsius_temperature,
            "get_currency": get_currency,
            "search_internet": search_internet,
            "update_field": self.writingRequirementsManager.update_field,
            "get_writing_requirement_field_content": self.writingRequirementsManager.get_field_content,
            "search_internet_for_report": search_internet_for_report,
            "write_report": write_report
        }
        self.model = model
       
    def analyze(self, user_message, tools):
        if not user_message or user_message.strip() == "":
            return {"type": "error", "message": "입력이 비어있습니다. 질문을 입력해주세요."}
    
            # 1. 모델 호출
        response = client.responses.create(
            model=model.o3_mini,
            input=user_message,
            tools=tools,
            tool_choice="auto",
            
        )
        return response.output
    

    def run(self, analyzed,context):
 
        context.append(analyzed)
        for tool_call in analyzed:
            if tool_call.get("type") != "function_call":
                continue
            function=tool_call["function"]
            func_name=function["name"]
            #실제 함수와 연결
            func_to_call = self.available_functions[func_name]

            try:

                func_args=json.loads(function["arguments"])#딕셔너리로 변환-> 문자열이 json형태입-> 이걸 딕셔너리로 변환
                
                if func_name == "search_internet":
                    # context는 이미 run 메서드의 매개변수로 받고 있음
                    func_response = func_to_call(chat_context=context[:], **func_args)
                else:
                    func_response=func_to_call(**func_args)
                context.append({
                    "tool_call_id": tool_call["id"],
                    "role": "tool",
                    "name": func_name, 
                    "content": str(func_response),
                    "parallel_tool_calls": True
                })#실행 결과를 문맥에 추가
  

            except Exception as e:
                print("Error occurred(run):",e)
                return makeup_response("[run 오류입니다]")
        return client.responses.create(model=self.model,input=context).model_dump()
    
    def run_report(self, analyzed_dict, context):
        func_name = analyzed_dict["function_call"]["name"]
        func_to_call = self.available_functions[func_name]        
        try:
            func_args = json.loads(analyzed_dict["function_call"]["arguments"])
            # 챗GPT가 알려주는 매개변수명과 값을 입력값으로하여 실제 함수를 호출한다.
            func_response = func_to_call(**func_args)
            context.append({
                "role": "function", 
                "name": func_name, 
                "content": str(func_response)
            })
            return client.chat.completions.create(model=self.model,messages=context).model_dump()            
        except Exception as e:
            print("Error occurred(run):",e)
            return makeup_response("[run 오류입니다]")

    def call_function(self, analyzed_dict):        
        func_name = analyzed_dict["function_call"]["name"]
        func_to_call = self.available_functions[func_name]                
        try:            
            func_args = json.loads(analyzed_dict["function_call"]["arguments"])
            func_response = func_to_call(**func_args)
            return str(func_response)
        except Exception as e:
            print("Error occurred(call_function):",e)
            return makeup_response("[call_function 오류입니다]")
    