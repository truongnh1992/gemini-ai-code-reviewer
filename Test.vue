<!-- UserProfile.vue -->
<template>
    <div class="profile-container">
      <!-- Security issue: Using v-html -->
      <div v-html="userBio"></div>
      
      <!-- Performance issue: Missing key in v-for -->
      <div v-for="post in userPosts">
        {{ post.title }}
      </div>
      
      <!-- Memory leak: Not cleaning up timer -->
      <div class="online-status">{{ onlineStatus }}</div>
      
      <!-- Missing data-qa/id for E2E testing -->
      <HButton @click="updateProfile">Update</HButton>
      
      <!-- CSS issues: Not following BEM, using Bootstrap classes -->
      <div class="container">
        <div class="profile-header row">
          <div class="col-md-6">
            <h1>{{ userName }}</h1>
          </div>
        </div>
      </div>
      
      <!-- Translation issues: Using deprecated v-trans directive and hardcoded English -->
      <div class="error-message">
        <div v-trans>An error occurred while loading the profile.</div>
        <Trans>Please try again later.</Trans>
      </div>
  
      <!-- Wrong prop naming convention -->
      <UserStats greeting_message="Hello" />
    </div>
  </template>
  
  <script>
  // Not using Composition API and TypeScript
  // Using Javascript instead of TypeScript
  export default {
    name: 'UserProfile',
  
    // Using interface instead of type for props
    props: {
      userId: {
        type: String,
        required: true
      },
      greeting_message: {  // Wrong prop naming convention
        type: String,
        default: ''
      }
    },
  
    // Using Vuex instead of Pinia
    computed: {
      ...mapGetters({
        // Wrong getter naming - using 'get' prefix
        profile: 'getUserProfile',
        settings: 'getSettings'
      })
    },
  
    data() {
      return {
        userName: 'John Doe',
        userBio: '<p>Welcome to my profile!</p>',
        userPosts: [],
        onlineStatus: 'Online',
        apiKey: 'sk_test_123456789',
        // Using non-Chargebee naming (deprecated)
        isChargebeeUser: true,
        isNonChargebeeUser: false,
        // Using index.ts for re-exporting (deprecated)
        utils: require('./utils/index.ts')
      }
    },
  
    mounted() {
      this.startTimer()
      this.fetchUserData()
      this.trackUserView()
    },
  
    methods: {
      // Wrong Amplitude property naming
      trackUserView() {
        amplitudeV2('view_profile', {
          'user-id': this.userId,
          'page_location': 'profile'  // Should be 'location'
        })
      },
  
      startTimer() {
        // Memory leak: Not storing timer reference
        setInterval(() => {
          this.checkOnlineStatus()
        }, 5000)
      },
  
      // Wrong API method naming convention
      async fetchUserData() {
        try {
          // Not using proper HTTP method prefix
          const response = await this.$api.getUserById(this.userId)
          this.userPosts = response.data.posts
        } catch {
          // Empty catch block - poor error handling
        }
      },
  
      checkOnlineStatus() {
        try {
          // API call without proper error handling
          this.$api.checkStatus()
        } catch {
          // Empty catch block
        }
      }
    }
  }
  </script>
  
  <style>
  /* Not using BEM methodology */
  .profile-container div button {
    background: blue;
  }
  
  .error-message {
    color: #ff0000;
    font-size: 14px;
  }
  
  /* Using utility classes directly instead of custom classes */
  .mt-4 {
    margin-top: 1rem;
  }
  .p-2 {
    padding: 0.5rem;
  }
  .text-center {
    text-align: center;
  }
  </style>
  