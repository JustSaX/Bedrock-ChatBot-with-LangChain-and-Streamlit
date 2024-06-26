import base64
import random
from io import BytesIO
from typing import List, Tuple, Union

import streamlit as st
from langchain.callbacks.base import BaseCallbackHandler
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferWindowMemory
from langchain.prompts.chat import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import StreamlitChatMessageHistory
from PIL import Image

from config import config
from models import ChatModel

INIT_MESSAGE = {
    "role": "assistant",
    "content": "Hi! I'm your AI Bot on Bedrock. How may I help you?",
}

CLAUDE_PROMPT = ChatPromptTemplate.from_messages(
    [
        MessagesPlaceholder(variable_name="history"),
        MessagesPlaceholder(variable_name="input"),
    ]
)


class StreamHandler(BaseCallbackHandler):
    """
    Callback handler to stream the generated text to Streamlit.
    """

    def __init__(self, container: st.container) -> None:
        self.container = container
        self.text = ""

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """
        Append the new token to the text and update the Streamlit container.
        """
        self.text += token
        self.container.markdown(self.text)


def set_page_config() -> None:
    """
    Set the Streamlit page configuration.
    """
    st.set_page_config(page_title="🤖 Chat with Bedrock", layout="wide")
    st.title("🤖 Chat with Bedrock")


def render_sidebar() -> Tuple[float, float, int, int, int, str]:
    """
    Render the sidebar UI and return the inference parameters.
    """
    with st.sidebar:
        st.markdown("## Inference Parameters")
        model_name_select = st.selectbox(
            'Model',
            list(config["models"].keys()),
            key=f"{st.session_state['widget_key']}_Model_Id",
        )

        st.session_state["model_name"] = model_name_select

        model_config = config["models"][model_name_select]

        system_prompt_disabled = model_config.get("system_prompt_disabled", False)
        system_prompt = st.text_area(
            "System Prompt",
            value=model_config.get("default_system_prompt", ""),
            key=f"{st.session_state['widget_key']}_System_Prompt",
            disabled=system_prompt_disabled,
        )

        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.0,
            value=model_config.get("temperature", 1.0),
            step=0.1,
            key=f"{st.session_state['widget_key']}_Temperature",
        )
        with st.container():
            col1, col2 = st.columns(2)
            with col1:
                top_p = st.slider(
                    "Top-P",
                    min_value=0.0,
                    max_value=1.0,
                    value=model_config.get("top_p", 1.0),
                    step=0.01,
                    key=f"{st.session_state['widget_key']}_Top-P",
                )
            with col2:
                top_k = st.slider(
                    "Top-K",
                    min_value=1,
                    max_value=model_config.get("max_top_k", 500),
                    value=model_config.get("top_k", 500),
                    step=5,
                    key=f"{st.session_state['widget_key']}_Top-K",
                )
        with st.container():
            col1, col2 = st.columns(2)
            with col1:
                max_tokens = st.slider(
                    "Max Token",
                    min_value=0,
                    max_value=4096,
                    value=model_config.get("max_tokens", 4096),
                    step=8,
                    key=f"{st.session_state['widget_key']}_Max_Token",
                )
            with col2:
                memory_window = st.slider(
                    "Memory Window",
                    min_value=0,
                    max_value=10,
                    value=model_config.get("memory_window", 10),
                    step=1,
                    key=f"{st.session_state['widget_key']}_Memory_Window",
                )

    model_kwargs = {
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
        "max_tokens": max_tokens,
    }
    if not model_config.get("system_prompt_disabled", False):
        model_kwargs["system"] = system_prompt


    return model_kwargs, memory_window


def init_conversationchain(chat_model: ChatModel, memory_window: int) -> ConversationChain:
    """
    Initialize the ConversationChain with the given parameters.
    """
    conversation = ConversationChain(
        llm=chat_model.llm,
        verbose=True,
        memory=ConversationBufferWindowMemory(
            k=memory_window,
            ai_prefix="Assistant",
            chat_memory=StreamlitChatMessageHistory(),
            return_messages=True,
        ),
        prompt=CLAUDE_PROMPT,
    )

    # Store LLM generated responses
    if "messages" not in st.session_state:
        st.session_state.messages = [INIT_MESSAGE]

    return conversation


def generate_response(
    conversation: ConversationChain, input: Union[str, List[dict]]
) -> str:
    """
    Generate a response from the conversation chain with the given input.
    """
    return conversation.invoke(
        {"input": input}, {"callbacks": [StreamHandler(st.empty())]}
    )


def new_chat() -> None:
    """
    Reset the chat session and initialize a new conversation chain.
    """
    st.session_state["messages"] = [INIT_MESSAGE]
    st.session_state["langchain_messages"] = []
    st.session_state["file_uploader_key"] = random.randint(1, 100)


def display_chat_messages(
    uploaded_files: List[st.runtime.uploaded_file_manager.UploadedFile]
) -> None:
    """
    Display chat messages and uploaded images in the Streamlit app.
    """
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if uploaded_files and "images" in message and message["images"]:
                display_images(message["images"], uploaded_files)

            if message["role"] == "user":
                display_user_message(message["content"])

            if message["role"] == "assistant":
                display_assistant_message(message["content"])


def display_images(
    image_ids: List[str],
    uploaded_files: List[st.runtime.uploaded_file_manager.UploadedFile],
) -> None:
    """
    Display uploaded images in the chat message.
    """
    num_cols = 10
    cols = st.columns(num_cols)
    i = 0

    for image_id in image_ids:
        for uploaded_file in uploaded_files:
            if image_id == uploaded_file.file_id:
                img = Image.open(uploaded_file)

                with cols[i]:
                    st.image(img, caption="", width=75)
                    i += 1

                if i >= num_cols:
                    i = 0


def display_user_message(message_content: Union[str, List[dict]]) -> None:
    """
    Display user message in the chat message.
    """
    if isinstance(message_content, str):
        st.markdown(message_content)
    elif isinstance(message_content, dict):
        st.markdown(message_content["input"][0]["content"][0]["text"])
    else:
        st.markdown(message_content[0]["text"])


def display_assistant_message(message_content: Union[str, dict]) -> None:
    """
    Display assistant message in the chat message.
    """
    if isinstance(message_content, str):
        st.markdown(message_content)
    elif "response" in message_content:
        st.markdown(message_content["response"])


def langchain_messages_format(
    messages: List[Union["AIMessage", "HumanMessage"]]
) -> List[Union["AIMessage", "HumanMessage"]]:
    """
    Format the messages for the LangChain conversation chain.
    """
    from langchain_core.messages import AIMessage, HumanMessage

    for i, message in enumerate(messages):
        if isinstance(message.content, list):
            if "role" in message.content[0]:
                if message.type == "ai":
                    message = AIMessage(message.content[0]["content"])
                if message.type == "human":
                    message = HumanMessage(message.content[0]["content"])
                messages[i] = message
    return messages


def display_uploaded_images(
    uploaded_files: List[st.runtime.uploaded_file_manager.UploadedFile],
    message_images_list: List[str],
    uploaded_file_ids: List[str],
) -> List[dict]:
    """
    Display uploaded images and return a list of image dictionaries for the prompt.
    """
    num_cols = 10
    cols = st.columns(num_cols)
    i = 0
    content_images = []

    for uploaded_file in uploaded_files:
        if uploaded_file.file_id not in message_images_list:
            uploaded_file_ids.append(uploaded_file.file_id)
            img = Image.open(uploaded_file)
            with BytesIO() as output_buffer:
                img.save(output_buffer, format=img.format)
                content_image = base64.b64encode(output_buffer.getvalue()).decode(
                    "utf8"
                )
            content_images.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": content_image,
                    },
                }
            )
            with cols[i]:
                st.image(img, caption="", width=75)
                i += 1
            if i >= num_cols:
                i = 0

    return content_images


def main() -> None:
    """
    Main function to run the Streamlit app.
    """
    set_page_config()

    # Generate a unique widget key only once
    if "widget_key" not in st.session_state:
        st.session_state["widget_key"] = str(random.randint(1, 1000000))

    # Add a button to start a new chat
    st.sidebar.button("New Chat", on_click=new_chat, type="primary")

    model_kwargs, memory_window = render_sidebar()
    chat_model = ChatModel(st.session_state["model_name"], model_kwargs)
    conv_chain = init_conversationchain(chat_model, memory_window)

    # Image uploader
    if "file_uploader_key" not in st.session_state:
        st.session_state["file_uploader_key"] = 0

    model_config = config["models"][st.session_state["model_name"]]
    image_upload_disabled = model_config.get("image_upload_disabled", False)
    uploaded_files = st.file_uploader(
        "Choose an image",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key=st.session_state["file_uploader_key"],
        disabled=image_upload_disabled,
    )

    # Display chat messages
    display_chat_messages(uploaded_files)

    # User-provided prompt
    prompt = st.chat_input()

    # Get images from previous messages
    message_images_list = [
        image_id
        for message in st.session_state.messages
        if message["role"] == "user"
        and "images" in message
        and message["images"]
        for image_id in message["images"]
    ]

    # Show image in corresponding chat box
    uploaded_file_ids = []
    if uploaded_files and len(message_images_list) < len(uploaded_files):
        with st.chat_message("user"):
            content_images = display_uploaded_images(
                uploaded_files, message_images_list, uploaded_file_ids
            )

            if prompt:
                formatted_prompt = chat_model.format_prompt(prompt)
                for content_image in content_images:
                    formatted_prompt.append(content_image)
                st.session_state.messages.append(
                    {"role": "user", "content": formatted_prompt, "images": uploaded_file_ids}
                )
                st.markdown(prompt)

    elif prompt:
        formatted_prompt = chat_model.format_prompt(prompt)
        st.session_state.messages.append({"role": "user", "content": formatted_prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

    # Modify langchain_messages format
    st.session_state["langchain_messages"] = langchain_messages_format(
        st.session_state["langchain_messages"]
    )

    # Generate a new response if last message is not from assistant
    if st.session_state.messages[-1]["role"] != "assistant":
        with st.chat_message("assistant"):
            response = generate_response(
                conv_chain, [{"role": "user", "content": formatted_prompt}]
            )
        message = {"role": "assistant", "content": response}
        st.session_state.messages.append(message)


if __name__ == "__main__":
    main()