*This project is based on two-way TCP file transfer between client and server*
*The program will enable the client to upload and download files through TCP protocol*
*KEY FEATURES:*
    *Upload to server*
    *Download from server*
    *Network protocol: TCP*
    *IP addressing*
    *GUI*
    *Error handling for fatal errors*
    *secure and reliable file transferring*
   *HOW TO USE*
      *Before knowing how to use the app, the app's latest version uses advanced ways of using it* User will need to have an environment best for ssl security.*
         *Seting up the environment*
            *If you are a developer I assume you are aware of Git and that the git is installed in your system, if not go ahead and install git*
               *Run git bash and navigate to the directory where this app is as: cd "the directory"*
                  *in git bash it will look like this: username@COMPUTER-NAME MINGW64 /c/Users/.../Client
                                                      $ .*
                     *Type in the command: openssl req -new -x509 -days 365 -nodes -out cert.pem -keyout key.pem*
                     *After running this command you will be asked to give your detais like, name, email, country, among others*
                     *If you want to keep them defaul go ahead and click enter. Two files namely: cert.pem and key.pem will appear in your directory, thats all.*
                     *You can now run the python app fie*
                     *For those who are not developers you can download the package and install it, it will have everything needed in it except for the source code.*
*RUNNING THE APP AS SEVER*
   *In the beautiful looking interface there are two sections, server and client. The server one is not complicated.*
   *Set port number of which you want the server yo be running on and check the "Use ssl/slt" checkbox*
   *Start the server with the button "Start server"*
      *This will start your machine to run as the server and the checked box will help in giving real-time updated list to anyone who will be connected to the server (Client)*
      *This will also trigger a listening mechanism of the app to start listening on incoming communications from the client for download and upload, including the listing of the server's list of items*
      *With thses three simple steps the server is ready*

*RUNNING THE APP AS CLIENT*
   *Though the client section looks a bit complex, it is not that complex as it seems.*
   *Imput the server's IP adress and Port number.*
   *Check on "USE SSL/SLT" to connected to the server and get realtime response (eg. The list of things the server is keeping) and also to generate certificates for encryption.*
   *click on "upload file" if you want to upload a file*
      *Select the file in the explorer and click okay*
         *You will see a log in the log field about uploading progress and uploading seccess or failure message.*
         *!Make sure the server is turned on when communicating and transfering the files.!*
   *Download made simple, instead of the old way in previous versions where we were supposed to pass in the exact file name to dowload, now with the the added technology of ssl we will be just selecting file: HOW THIS WORKS*
      *In client section, click on "REFRESH LIST", the list of thing in the server will be shown in the dialog box, if the server is on.*
      *select the file you want to download by clicking it*
      *Click on "Downoad Selected" and then the downloading will beging. The log box will show the download progress and success infor if the process did not caught any error, if the error has be caught it will be explicitly explained in the log box.*

ERROR HANDLING

