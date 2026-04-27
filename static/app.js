const state = {
  user: JSON.parse(window.localStorage.getItem("commerceUser") || "null"),
  products: [],
  categories: [],
  cart: [],
  total: 0,
  search: new URLSearchParams(window.location.search).get("search") || "",
  category: "all",
};

const authScreen = document.querySelector("#auth-screen");
const appScreen = document.querySelector("#app-screen");
const loginForm = document.querySelector("#login-form");
const registerForm = document.querySelector("#register-form");
const showLogin = document.querySelector("#show-login");
const showRegister = document.querySelector("#show-register");
const authStatus = document.querySelector("#auth-status");
const sessionLabel = document.querySelector("#session-label");
const accountName = document.querySelector("#account-name");
const accountEmail = document.querySelector("#account-email");
const accountRole = document.querySelector("#account-role");
const adminPanel = document.querySelector("#admin-panel");
const adminTitle = document.querySelector("#admin-title");
const productForm = document.querySelector("#product-form");
const productStatus = document.querySelector("#product-status");
const updatedProduct = document.querySelector("#updated-product");
const productSubmit = document.querySelector("#product-submit");
const cancelEdit = document.querySelector("#cancel-edit");
const categoryOptions = document.querySelector("#category-options");
const productGrid = document.querySelector("#product-grid");
const resultCount = document.querySelector("#result-count");
const categorySelect = document.querySelector("#category");
const searchInput = document.querySelector("#search");
const cartPanel = document.querySelector("#cart-panel");
const cartItems = document.querySelector("#cart-items");
const cartCount = document.querySelector("#cart-count");
const cartTotal = document.querySelector("#cart-total");
const checkoutStatus = document.querySelector("#checkout-status");
const paymentForm = document.querySelector("#payment-form");
const paymentMethod = document.querySelector("#payment-method");
const paymentTitle = document.querySelector("#payment-title");
const paymentDescription = document.querySelector("#payment-description");
const shippingAddress = document.querySelector("#shipping-address");
const shippingCity = document.querySelector("#shipping-city");
const shippingPincode = document.querySelector("#shipping-pincode");
const toast = document.querySelector("#toast");

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

function money(value) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value);
}

function currentUserId() {
  return state.user?.id || 0;
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 2400);
}

function setAuthMode(mode) {
  const loginMode = mode === "login";
  loginForm.classList.toggle("hidden", !loginMode);
  registerForm.classList.toggle("hidden", loginMode);
  showLogin.classList.toggle("active", loginMode);
  showRegister.classList.toggle("active", !loginMode);
  authStatus.textContent = "";
}

function setUser(user) {
  state.user = user;
  window.localStorage.setItem("commerceUser", JSON.stringify(user));
  renderSession();
}

function clearUser() {
  state.user = null;
  window.localStorage.removeItem("commerceUser");
  state.cart = [];
  state.total = 0;
  renderSession();
}

function renderSession() {
  const signedIn = Boolean(state.user);
  authScreen.classList.toggle("hidden", signedIn);
  appScreen.classList.toggle("hidden", !signedIn);
  if (!signedIn) {
    return;
  }

  sessionLabel.textContent = `Signed in as ${state.user.name} (${state.user.role})`;
  accountName.textContent = state.user.name;
  accountEmail.textContent = state.user.email;
  accountRole.textContent = state.user.role === "admin" ? "Admin account" : "User account";
  adminPanel.classList.toggle("hidden", state.user.role !== "admin");
  searchInput.value = state.search;
  loadProducts();
  loadCart();
}

async function loadProducts() {
  if (!state.user) return;
  const params = new URLSearchParams({
    user_id: currentUserId(),
    search: state.search,
    category: state.category,
  });
  const data = await api(`/api/products?${params.toString()}`);
  state.products = data.products;
  state.categories = data.categories;
  renderCategories();
  renderProducts();
}

function renderCategories() {
  const current = categorySelect.value || state.category;
  categorySelect.innerHTML = [
    `<option value="all">All categories</option>`,
    ...state.categories.map((category) => `<option value="${category}">${category}</option>`),
  ].join("");
  categorySelect.value = state.categories.includes(current) ? current : "all";
  categoryOptions.innerHTML = state.categories.map((category) => `<option value="${category}"></option>`).join("");
}

function renderProducts() {
  resultCount.textContent = `${state.products.length} product${state.products.length === 1 ? "" : "s"} available`;
  if (state.products.length === 0) {
    productGrid.innerHTML = `<p>No products match your search.</p>`;
    return;
  }
  productGrid.innerHTML = state.products
    .map((product) => {
      const changed = Math.abs(product.dynamic_price - product.base_price) >= 0.01;
      const actionButton =
        state.user.role === "admin"
          ? `<button type="button" data-edit="${product.id}">Edit product</button>`
          : `<button type="button" data-add="${product.id}">Add to cart</button>`;
      const adminBadge = product.added_by_role === "admin" ? `<span class="admin-badge">Admin added</span>` : "";
      return `
        <article class="product-card">
          <img src="${product.image_url}" alt="${product.name}" loading="lazy" />
          <div class="product-body">
            <div class="product-title">
              <h3>${product.name}</h3>
              <div class="card-badges">
                <span class="badge">${product.category}</span>
                ${adminBadge}
              </div>
            </div>
            <p class="description">${product.description}</p>
            <div class="price-row">
              <span class="price">${money(product.dynamic_price)}</span>
              ${changed ? `<span class="base-price">${money(product.base_price)}</span>` : ""}
            </div>
            <p class="pricing-note">Price adjusted for ${product.pricing.explanation}.</p>
            <p class="stock">${product.stock} in stock - Rating ${product.rating}</p>
            ${actionButton}
          </div>
        </article>
      `;
    })
    .join("");
}

function renderUpdatedProduct(product, mode) {
  updatedProduct.classList.remove("hidden");
  updatedProduct.innerHTML = `
    <div>
      <p class="eyebrow">${mode === "edit" ? "Updated product" : "Added product"}</p>
      <h3>${product.name}</h3>
    </div>
    <dl class="updated-product-grid">
      <div>
        <dt>Category</dt>
        <dd>${product.category}</dd>
      </div>
      <div>
        <dt>Base price</dt>
        <dd>${money(product.base_price)}</dd>
      </div>
      <div>
        <dt>Dynamic price</dt>
        <dd>${money(product.dynamic_price)}</dd>
      </div>
      <div>
        <dt>Stock</dt>
        <dd>${product.stock} / ${product.max_stock}</dd>
      </div>
      <div>
        <dt>Rating</dt>
        <dd>${product.rating}</dd>
      </div>
    </dl>
    <p>${product.description}</p>
  `;
}

async function loadCart() {
  if (!state.user) return;
  const data = await api(`/api/cart?user_id=${currentUserId()}`);
  state.cart = data.items;
  state.total = data.total;
  renderCart();
}

function renderCart() {
  const count = state.cart.reduce((sum, item) => sum + item.quantity, 0);
  cartCount.textContent = count;
  cartTotal.textContent = money(state.total);
  updatePaymentCopy();
  if (state.cart.length === 0) {
    cartItems.innerHTML = `<p>Your cart is empty.</p>`;
    return;
  }
  cartItems.innerHTML = state.cart
    .map(
      (item) => `
        <article class="cart-item">
          <h3>${item.name}</h3>
          <div class="quantity-row">
            <label>
              Quantity
              <input type="number" min="0" max="${item.stock}" value="${item.quantity}" data-quantity="${item.id}" />
            </label>
            <strong>${money(item.line_total)}</strong>
          </div>
          <p class="stock">${money(item.price)} each - ${item.stock} available</p>
        </article>
      `,
    )
    .join("");
}

async function addToCart(productId) {
  await api("/api/cart", {
    method: "POST",
    body: JSON.stringify({ user_id: currentUserId(), product_id: productId, quantity: 1 }),
  });
  await loadCart();
  await loadProducts();
  showToast("Added to cart. Price signals updated.");
}

async function updateCart(productId, quantity) {
  const data = await api("/api/cart", {
    method: "PATCH",
    body: JSON.stringify({ user_id: currentUserId(), product_id: productId, quantity }),
  });
  state.cart = data.items;
  state.total = data.total;
  renderCart();
}

async function checkout() {
  checkoutStatus.textContent = "";
  if (state.cart.length === 0) {
    checkoutStatus.textContent = "Add a product to cart before payment.";
    return;
  }
  if (shippingAddress.value.trim().length < 10 || shippingCity.value.trim().length < 2 || shippingPincode.value.trim().length < 5) {
    checkoutStatus.textContent = "Add your complete delivery address before placing the order.";
    return;
  }
  const method = paymentMethod.value;
  const reference = `DC-${method.toUpperCase()}-${Date.now()}`;
  try {
    const order = await api("/api/checkout", {
      method: "POST",
      body: JSON.stringify({
        user_id: currentUserId(),
        payment_method: method,
        payment_token: method === "cod" ? "" : `approved-${reference}`,
        payment_reference: reference,
        shipping_address: shippingAddress.value.trim(),
        shipping_city: shippingCity.value.trim(),
        shipping_pincode: shippingPincode.value.trim(),
      }),
    });
    checkoutStatus.textContent =
      method === "cod"
        ? `Order #${order.order_id} placed for ${money(order.total)}. Delivery to ${order.shipping_city} ${order.shipping_pincode}. Payment pending on delivery.`
        : `Order #${order.order_id} paid ${money(order.total)} through ${method.toUpperCase()}. Delivery to ${order.shipping_city} ${order.shipping_pincode}. Reference: ${order.payment_reference}.`;
    await loadCart();
    await loadProducts();
    paymentForm.reset();
    updatePaymentCopy();
    showToast("Order placed successfully.");
  } catch (error) {
    checkoutStatus.textContent = error.message;
  }
}

function updatePaymentCopy() {
  const payable = money(state.total || 0);
  const copy = {
    upi: ["UPI demo payment", `Pay exactly ${payable}. A test UPI transaction will be generated.`],
    card: ["Card demo payment", `Pay exactly ${payable}. No real card details are collected.`],
    wallet: ["Wallet demo payment", `Pay exactly ${payable}. A test wallet reference will be generated.`],
    cod: ["Cash on delivery", `Place the order for ${payable} and pay on delivery.`],
  };
  const [title, description] = copy[paymentMethod.value];
  paymentTitle.textContent = title;
  paymentDescription.textContent = description;
  document.querySelector("#checkout").textContent =
    paymentMethod.value === "cod" ? "Place order" : "Pay and place order";
}

async function addProduct(form) {
  const formData = new FormData(form);
  const productId = String(formData.get("product_id") || "");
  productStatus.textContent = "";
  const payload = {
    admin_user_id: currentUserId(),
    product_id: Number(productId),
    name: formData.get("name"),
    category: formData.get("category"),
    description: formData.get("description"),
    base_price: Number(formData.get("base_price")),
    stock: Number(formData.get("stock")),
    max_stock: Number(formData.get("max_stock")),
    rating: Number(formData.get("rating")),
    image_url: formData.get("image_url"),
  };
  try {
    const editing = Boolean(productId);
    const data = await api("/api/products", {
      method: editing ? "PATCH" : "POST",
      body: JSON.stringify(payload),
    });
    resetProductForm();
    state.category = "all";
    productStatus.textContent = editing
      ? `${data.product.name} was updated.`
      : `${data.product.name} was added to the product list.`;
    renderUpdatedProduct(data.product, editing ? "edit" : "add");
    await loadProducts();
    showToast(editing ? "Product updated." : "Product added to catalog.");
  } catch (error) {
    productStatus.textContent = error.message;
  }
}

function editProduct(productId) {
  const product = state.products.find((item) => item.id === productId);
  if (!product) return;
  productForm.elements.product_id.value = product.id;
  productForm.elements.name.value = product.name;
  productForm.elements.category.value = product.category;
  productForm.elements.base_price.value = Math.round(product.base_price);
  productForm.elements.stock.value = product.stock;
  productForm.elements.max_stock.value = product.max_stock;
  productForm.elements.rating.value = product.rating;
  productForm.elements.image_url.value = product.image_url;
  productForm.elements.description.value = product.description;
  adminTitle.textContent = "Edit product";
  productSubmit.textContent = "Update product";
  cancelEdit.classList.remove("hidden");
  productStatus.textContent = `Editing ${product.name}.`;
  updatedProduct.classList.add("hidden");
  updatedProduct.innerHTML = "";
  adminPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

function resetProductForm() {
  productForm.reset();
  productForm.elements.product_id.value = "";
  productForm.elements.rating.value = "4.5";
  adminTitle.textContent = "Add a product";
  productSubmit.textContent = "Add product";
  cancelEdit.classList.add("hidden");
}

async function login(form) {
  const formData = new FormData(form);
  authStatus.textContent = "";
  try {
    const data = await api("/api/login", {
      method: "POST",
      body: JSON.stringify({
        email: formData.get("email"),
        password: formData.get("password"),
      }),
    });
    setUser(data.user);
  } catch (error) {
    authStatus.textContent = error.message;
  }
}

async function register(form) {
  const formData = new FormData(form);
  const email = formData.get("email");
  authStatus.textContent = "";
  try {
    await api("/api/register", {
      method: "POST",
      body: JSON.stringify({
        name: formData.get("name"),
        email,
        password: formData.get("password"),
      }),
    });
    clearUser();
    form.reset();
    setAuthMode("login");
    loginForm.elements.email.value = email;
    loginForm.elements.password.value = "";
    authStatus.textContent = "Account registered successfully. Please sign in.";
  } catch (error) {
    authStatus.textContent = error.message;
  }
}

let searchTimer;
searchInput.addEventListener("input", (event) => {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => {
    state.search = event.target.value;
    const params = new URLSearchParams(window.location.search);
    if (state.search) {
      params.set("search", state.search);
    } else {
      params.delete("search");
    }
    window.history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`);
    loadProducts();
  }, 180);
});

categorySelect.addEventListener("change", (event) => {
  state.category = event.target.value;
  state.search = "";
  searchInput.value = "";
  window.history.replaceState(null, "", window.location.pathname);
  loadProducts();
});

productGrid.addEventListener("click", (event) => {
  const addButton = event.target.closest("[data-add]");
  if (addButton) {
    addToCart(Number(addButton.dataset.add));
    return;
  }
  const editButton = event.target.closest("[data-edit]");
  if (editButton) {
    editProduct(Number(editButton.dataset.edit));
  }
});

productGrid.addEventListener("pointerover", (event) => {
  const card = event.target.closest(".product-card");
  const button = card?.querySelector("[data-add]");
  if (button && state.user) {
    api("/api/events", {
      method: "POST",
      body: JSON.stringify({ user_id: currentUserId(), product_id: Number(button.dataset.add), event_type: "view" }),
    }).catch(() => {});
  }
});

cartItems.addEventListener("change", (event) => {
  const input = event.target.closest("[data-quantity]");
  if (input) {
    updateCart(Number(input.dataset.quantity), Number(input.value));
  }
});

document.querySelector(".cart-toggle").addEventListener("click", () => {
  cartPanel.classList.add("open");
});

document.querySelector(".cart-close").addEventListener("click", () => {
  cartPanel.classList.remove("open");
});

paymentMethod.addEventListener("change", updatePaymentCopy);
paymentForm.addEventListener("submit", (event) => {
  event.preventDefault();
  checkout();
});
document.querySelector("#logout").addEventListener("click", clearUser);
showLogin.addEventListener("click", () => setAuthMode("login"));
showRegister.addEventListener("click", () => setAuthMode("register"));
loginForm.addEventListener("submit", (event) => {
  event.preventDefault();
  login(loginForm);
});
registerForm.addEventListener("submit", (event) => {
  event.preventDefault();
  register(registerForm);
});
productForm.addEventListener("submit", (event) => {
  event.preventDefault();
  addProduct(productForm);
});
cancelEdit.addEventListener("click", () => {
  resetProductForm();
  productStatus.textContent = "";
  updatedProduct.classList.add("hidden");
  updatedProduct.innerHTML = "";
});

setAuthMode("login");
updatePaymentCopy();
renderSession();
