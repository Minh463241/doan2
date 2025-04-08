document.addEventListener("DOMContentLoaded", function () {
  // --- Slide Show ---
  const slides = document.querySelectorAll('.slider .slide');
  let currentSlide = 0;
  if (slides.length === 0) {
    console.log("Không có slide nào được tìm thấy");
  } else {
    setInterval(() => {
      slides[currentSlide].classList.remove('active');
      currentSlide = (currentSlide + 1) % slides.length;
      slides[currentSlide].classList.add('active');
    }, 5000); // Chuyển slide mỗi 5 giây
  }

  // --- User Menu Dropdown ---
  const userMenuButton = document.getElementById("userMenuButton");
  const userMenu = document.getElementById("userMenu");
  if (userMenuButton && userMenu) {
    userMenuButton.addEventListener("click", function (e) {
      e.stopPropagation(); // Ngăn chặn hành động lan truyền
      userMenu.classList.toggle("hidden");
    });
  }
  // Đóng dropdown khi click bên ngoài
  document.addEventListener("click", function () {
    if (userMenu && !userMenu.classList.contains("hidden")) {
      userMenu.classList.add("hidden");
    }
  });

  // --- Chat Widget ---
  const chatToggle = document.getElementById('chat-toggle');
  const chatBox = document.getElementById('chat-box');
  const chatClose = document.getElementById('chat-close');
  if (chatToggle && chatBox) {
    chatToggle.addEventListener('click', () => {
      chatBox.classList.toggle('hidden');
    });
  }
  if (chatClose && chatBox) {
    chatClose.addEventListener('click', () => {
      chatBox.classList.add('hidden');
    });
  }
 

  // Gửi tin nhắn chat và xử lý phản hồi từ server LLM
  const chatSendButton = document.getElementById('chat-send');
  if (chatSendButton) {
    chatSendButton.addEventListener('click', () => {
      const chatInput = document.getElementById('chat-input');
      const message = chatInput.value.trim();
      if (message === "") return;

      // Hiển thị tin nhắn của người dùng
      const chatContent = document.getElementById('chat-content');
      const userMessageDiv = document.createElement('div');
      userMessageDiv.classList.add('mb-2', 'text-right');
      userMessageDiv.innerHTML = `<span class="bg-blue-500 text-white px-3 py-1 rounded inline-block">${message}</span>`;
      chatContent.appendChild(userMessageDiv);
      chatInput.value = "";

      // Gửi tin nhắn đến server LLM (địa chỉ endpoint theo ví dụ của bạn)
      fetch("http://localhost:8000/ask/", {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify({ question: message })
      })
      .then(response => response.json())
      .then(data => {
        // Kiểm tra cấu trúc của data để lấy phản hồi đúng
        const responseText = data.response || data.answer || "Không có phản hồi";
        const botMessageDiv = document.createElement('div');
        botMessageDiv.classList.add('mb-2', 'text-left');
        botMessageDiv.innerHTML = `<span class="bg-gray-300 text-gray-800 px-3 py-1 rounded inline-block">${responseText}</span>`;
        chatContent.appendChild(botMessageDiv);
        // Cuộn xuống dưới cùng
        chatContent.scrollTop = chatContent.scrollHeight;
      })
      .catch(error => {
        const errorDiv = document.createElement('div');
        errorDiv.classList.add('mb-2', 'text-left');
        errorDiv.innerHTML = `<span class="bg-red-300 text-red-800 px-3 py-1 rounded inline-block">Lỗi: ${error}</span>`;
        chatContent.appendChild(errorDiv);
      });
    });
  }
});
