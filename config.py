from supabase import create_client, Client
class Config:
    
    SUPABASE_URL = "https://uaggzmqpvbtrinppmhrc.supabase.co"
    SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVhZ2d6bXFwdmJ0cmlucHBtaHJjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQwNzc0NjYsImV4cCI6MjA1OTY1MzQ2Nn0.Zc0ZUaYIi93E_xJ067M2c5gmY-WbHIG0epYvy3HureM"

    CLOUDINARY_CLOUD_NAME = "dwczro6hp"
    CLOUDINARY_API_KEY = "648677879979597"
    CLOUDINARY_API_SECRET = "-1D5fNq5hrtfGoIeZ8U7n8GHWi0"
    
    PAYPAL_MODE = "sandbox"
    PAYPAL_CLIENT_ID = "AWsHRyezYDAKZLpJRjtJz2gmGbSJKnNSM9m5YKqOF0QIcpc19g9npAJX_W9zijWkORfHn4xRBgkW-MCX"
    PAYPAL_CLIENT_SECRET = "EFHP2SK80y2L3Q-8R9o_QQpbB0-cK848UyTr0YqVllZ8l8qe_DiGrQgUvq6N_V7ESxedUIXgeQtu5zfC"

    PAYPAL_CLIENT_SECRET = "EFHP2SK80y2L3Q-8R9o_QQpbB0-cK848UyTr0YqVllZ8l8qe_DiGrQgUvq6N_V7ESxedUIXgeQtu5zfC"
supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)