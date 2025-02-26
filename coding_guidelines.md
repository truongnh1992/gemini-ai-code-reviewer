## Coding Guidelines

### Amplitude
- When passing a query parameter to be used for Amplitude's location parameter, ensure that the query parameter is named `location`.

### CSS
- Don't use Bootstrap classes in new components.
- If using more than two utility classes, those should be remade using custom classes.
- Check if typography classes can be remade into mixins so they can be reused within custom classes.
- **Use BEM (Block Element Modifier) methodology** for writing CSS classes.

### Tools
- Use either VS Code or WebStorm.
- Try out GitHub Copilot.

### Writing Good Commit Messages
- Limit the subject line to 50 characters and wrap the body at 72 characters.
- Separate the subject from the body with a newline.
- Do not end the subject line with a period.
- Use the body to explain *what* and *why* as opposed to *how*.
- Use imperative mood in the subject line.

### Naming Conventions
#### File Naming
- Image files - `kebab-case`
- Vue component files - `PascalCase`
- All other project files - `camelCase`

#### Component Property Name
- Use `camelCase` when declaring:
  ```ts
  defineProps<{ greetingMessage: string }>()
  ```
- Use `kebab-case` when passing props to a child component:
  ```vue
  <MyComponent greeting-message="hello" />
  ```
- Follow the official Vue.js documentation approach.

#### Amplitude Property Name
- Use `camelCase` when passing additional properties to an Amplitude event:
  ```ts
  amplitudeV2(eventName, {
    propertyToPass: value
  });
  ```

### Vuex
- API calls meant to get information should have a `fetch` prefix.
- Getters should be named without a `get` prefix unless it's a function.
  ```ts
  getSomethingWithParam: () => (parameter) => '',
  something: () => ''
  ```

### API
- Each HTTP method should have its own prefix:
  ```ts
  get: {
    getUsersById: () => {},
    getSomething: () => {}
  },
  post: {
    postUser: () => {},
    postClientInformation: () => {},
    createUser: () => {},
    updateUser: () => {},
    createClientInformation: () => {},
    updateClientInformation: () => {}
  },
  patch: {
    patchUserInformation: () => {}
  },
  put: {
    putUserInformation: () => {}
  },
  delete: {
    deleteUserById: () => {}
  }
  ```
- Only `post` method can have variations like `post/update/create`.

### Basic Composables
- Avoid creating very basic composables (e.g., `useToggle`) if they don't bring significant value.

### Interfaces
- Prefix interface names with `I` to avoid name clashes with enums (e.g., `IProps`, `IAccount`).

### Button Attributes for E2E Tests
- All new `HButton` instances should use `data-qa`/`id` attributes to assist QA in constructing e2e tests.
- Avoid using auto-generated `v-qa-generate` tags unless necessary.

### Deprecations
- **Javascript files** → Use TypeScript instead. Acceptable to use `@ts-ignore` for initial refactor.
- **Vue Options API** → Use Vue Composition API with `<script setup>`.
- **Vuex** → Use Pinia instead.
- **Chargebee/non-Chargebee naming** → Legacy logic, avoid using.
- **Directive `v-trans` and component `Trans`** → Use `t()` function instead. Place inside `v-safe-html` for translated HTML content.
- **Interface keyword for Props or Emits** → Use `type` instead.
- **Avoid `index.ts` for re-exporting** due to circular dependencies.

### Translation Slugs
- All new files must use slugs for translations in the `hpanel` project.
- PRs with hardcoded English text instead of slugs should not be approved.

### Testing
- All new `.vue` files must have corresponding tests created.

# Vue Component Guidelines

## General Guidelines
- Use Composition API for all new components
- All components must have TypeScript type definitions
- Add data-test attributes for E2E testing
- Follow the Single Responsibility Principle

## Security Guidelines
- Never use v-html directive unless absolutely necessary and content is sanitized
- Don't store sensitive information (API keys, tokens) in component files
- Always validate and sanitize user inputs
- Use HTTPS for all API calls

## Performance Guidelines
- Always use key attribute with v-for directives
- Avoid deep nesting of components
- Use lazy loading for heavy components
- Clean up event listeners and timers in beforeUnmount

## CSS Guidelines
- Follow BEM methodology for CSS class naming
- Use CSS variables for colors, spacing, and other repeated values
- Avoid using global CSS frameworks (Bootstrap, etc.)
- Use utility classes sparingly and document their usage

## Component Naming and Structure
- Use PascalCase for component file names
- Use camelCase for prop names
- Use kebab-case for event names
- Group related components in feature-specific directories

## State Management
- Use Pinia for global state management
- Keep component state minimal
- Document state dependencies
- Use computed properties for derived state

## API Integration
- Use environment variables for API endpoints
- Implement proper error handling
- Use typed API responses
- Document API dependencies

## Translation Guidelines
- Use vue-i18n for all text content
- No hardcoded English text in components
- Use translation keys with proper namespacing
- Document translation requirements

## Error Handling
- Implement proper error boundaries
- Log errors appropriately
- Show user-friendly error messages
- Handle all possible error states

## Testing Guidelines
- Write unit tests for all components
- Include E2E tests for critical paths
- Test error scenarios
- Document test coverage requirements

